"""Streaming execution for queries and chat.

Handles streaming responses with reasoning steps and token-by-token output.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from collections.abc import AsyncGenerator, Callable, Iterator
from contextlib import aclosing
from typing import TYPE_CHECKING
from uuid import uuid4

from starlette.requests import ClientDisconnect

from backend.errors import ApplicationError, correlation_context, report_failure, stage_context
from backend.models import (
    EXECUTION_EVENT_ADAPTER,
    CompleteEvent,
    CompleteFrame,
    ErrorCode,
    ErrorEvent,
    ErrorFrame,
    ExecutionEvent,
    SourcesEvent,
    SourcesFrame,
    StepEvent,
    StepFrame,
    TokenEvent,
    TokenFrame,
)
from backend.querying.nodes import generate_stream, grade, retrieve, rewrite_query
from backend.sources import build_sources

if TYPE_CHECKING:
    from backend.config import Settings
    from backend.models import KBManifest
    from backend.storage.vector import VectorStore


def _sse(event: ExecutionEvent) -> str:
    """Validate the serialized envelope, then derive both SSE fields from it."""
    validated = EXECUTION_EVENT_ADAPTER.validate_json(
        event.model_dump_json(warnings="error"), strict=True
    )
    payload = validated.data.model_dump_json(exclude_none=validated.type == "error")
    return f"event: {validated.type}\ndata: {payload}\n\n"


async def stream_query(
    question: str,
    kb: tuple[KBManifest, VectorStore],
    settings: Settings,
) -> AsyncGenerator[str, None]:
    """Stream a query with one correlated terminal failure boundary."""
    async with aclosing(_safe_stream(_query(question, kb, settings), "query")) as events:
        async for event in events:
            yield event


async def _safe_stream(
    events: AsyncGenerator[str, None], operation: str
) -> AsyncGenerator[str, None]:
    correlation_token = correlation_context.set(correlation_context.get() or str(uuid4()))
    stage_token = stage_context.set(f"{operation}.initialize")
    try:
        try:
            async with aclosing(events):
                async for event in events:
                    yield event
        except ClientDisconnect:
            raise
        except Exception as exc:
            failure = report_failure(exc)
            yield _sse(ErrorFrame(data=ErrorEvent(error=failure.envelope.error)))
    finally:
        stage_context.reset(stage_token)
        correlation_context.reset(correlation_token)


async def _stream_tokens(
    produce: Callable[[], Iterator[str]], timeout: float
) -> AsyncGenerator[str, None]:
    """Move typed worker failures to the request context; stop on idle expiry."""
    q: queue.Queue[tuple[str, str | Exception | None]] = queue.Queue()
    stopped = threading.Event()

    def worker() -> None:
        try:
            iterator = produce()
            try:
                for token in iterator:
                    if stopped.is_set():
                        return
                    q.put(("token", token))
            finally:
                close = getattr(iterator, "close", None)
                if close is not None:
                    close()
            if not stopped.is_set():
                q.put(("done", None))
        except Exception as exc:
            if not stopped.is_set():
                q.put(("error", exc))

    threading.Thread(target=worker, daemon=True).start()
    try:
        while True:
            try:
                event_type, data = await asyncio.to_thread(q.get, timeout=timeout)
            except queue.Empty:
                raise ApplicationError(ErrorCode.PROVIDER_TIMEOUT) from None
            if event_type == "done":
                return
            if isinstance(data, Exception):
                raise data
            if isinstance(data, str):
                yield data
    finally:
        stopped.set()


async def _query(
    question: str,
    kb: tuple[KBManifest, VectorStore],
    settings: Settings,
) -> AsyncGenerator[str, None]:
    """Stream a RAG query with reasoning steps.

    Args:
        question: User question.
        kb: Tuple of (manifest, vector_store).
        settings: Application settings.

    Yields:
        SSE formatted strings for each event.
    """
    from backend.llm import get_llm

    _, store = kb
    llm = get_llm(settings)

    # Step 1: Analyzing
    yield _sse(
        StepFrame(
            data=StepEvent(
                type="analyzing",
                title="Analyzing question",
                description="Understanding your query...",
            )
        )
    )
    await asyncio.sleep(0.05)

    # Step 2: Rewrite query
    yield _sse(
        StepFrame(
            data=StepEvent(
                type="rewriting",
                title="Optimizing search",
                description="Creating an optimized search query...",
            )
        )
    )

    stage_context.set("query.rewrite")
    query = await asyncio.to_thread(rewrite_query, question, llm)

    # Step 3: Search
    yield _sse(
        StepFrame(
            data=StepEvent(
                type="searching",
                title="Searching documents",
                description=f"Searching for: {query[:50]}...",
                details={"query": query},
            )
        )
    )

    stage_context.set("query.retrieve")
    docs = await asyncio.to_thread(retrieve, query, store, settings.top_k)

    # Step 4: Grade
    yield _sse(
        StepFrame(
            data=StepEvent(
                type="grading",
                title="Evaluating results",
                description=f"Checking relevance of {len(docs)} documents...",
                details={"count": len(docs)},
            )
        )
    )

    stage_context.set("query.grade")
    docs = await asyncio.to_thread(grade, question, docs, llm)

    # Emit sources
    stage_context.set("query.sources")
    sources = build_sources(docs)

    if sources:
        yield _sse(SourcesFrame(data=SourcesEvent(sources=sources)))

    # Step 5: Generate with streaming
    yield _sse(
        StepFrame(
            data=StepEvent(
                type="generating",
                title="Generating answer",
                description=f"Synthesizing from {len(docs)} sources...",
            )
        )
    )

    full_answer = ""
    stage_context.set("query.generate")

    if llm is not None and hasattr(llm, "stream"):
        async with aclosing(
            _stream_tokens(lambda: generate_stream(question, docs, llm), 60.0)
        ) as tokens:
            async for token in tokens:
                full_answer += token
                yield _sse(TokenFrame(data=TokenEvent(token=token)))
    else:
        # Non-streaming fallback
        from backend.querying.nodes import generate

        full_answer = await asyncio.to_thread(generate, question, docs, llm)
        # Simulate streaming by chunking
        for i in range(0, len(full_answer), 4):
            yield _sse(TokenFrame(data=TokenEvent(token=full_answer[i : i + 4])))
            await asyncio.sleep(0.01)

    yield _sse(CompleteFrame(data=CompleteEvent(answer=full_answer)))


async def stream_chat(
    message: str,
    settings: Settings,
) -> AsyncGenerator[str, None]:
    """Stream chat with the same terminal failure semantics as HTTP/query."""
    async with aclosing(_safe_stream(_chat(message, settings), "chat")) as events:
        async for event in events:
            yield event


async def _chat(message: str, settings: Settings) -> AsyncGenerator[str, None]:
    """Stream a chat response.

    Args:
        message: User message to respond to.
        settings: Application settings.

    Yields:
        SSE formatted strings for each event.
    """
    from langchain_core.messages import HumanMessage

    from backend.llm import get_llm

    llm = get_llm(settings)

    if llm is None:
        raise ApplicationError(ErrorCode.MODEL_NOT_CONFIGURED)

    yield _sse(
        StepFrame(
            data=StepEvent(
                type="generating", title="Thinking", description="Processing your message..."
            )
        )
    )

    # Create simple message list
    lc_messages = [HumanMessage(content=message)]

    full_answer = ""
    stage_context.set("chat.generate")

    if hasattr(llm, "stream"):

        def produce() -> Iterator[str]:
            for chunk in llm.stream(lc_messages):
                token = getattr(chunk, "content", None)
                if token:
                    yield token

        async with aclosing(_stream_tokens(produce, 30.0)) as tokens:
            async for token in tokens:
                full_answer += token
                yield _sse(TokenFrame(data=TokenEvent(token=token)))
    else:
        response = await asyncio.to_thread(llm.invoke, lc_messages)
        full_answer = str(getattr(response, "content", response))
        for i in range(0, len(full_answer), 4):
            yield _sse(TokenFrame(data=TokenEvent(token=full_answer[i : i + 4])))
            await asyncio.sleep(0.01)

    yield _sse(CompleteFrame(data=CompleteEvent(answer=full_answer)))


__all__ = ["stream_query", "stream_chat"]
