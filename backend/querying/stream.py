"""Streaming execution for queries and chat.

Handles streaming responses with reasoning steps and token-by-token output.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING

from backend.querying.nodes import generate_stream, grade, retrieve, rewrite_query

if TYPE_CHECKING:
    from backend.config import Settings
    from backend.models import KBManifest
    from backend.storage.vector import VectorStore


def _sse(event: str, data: dict) -> str:
    """Format data as a Server-Sent Event.

    Args:
        event: Event type name.
        data: Event data dictionary.

    Returns:
        SSE formatted string.
    """
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def stream_query(
    question: str,
    kb: tuple[KBManifest, VectorStore],
    settings: Settings,
) -> AsyncIterator[str]:
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
    yield _sse("step", {
        "type": "analyzing",
        "title": "Analyzing question",
        "description": "Understanding your query...",
    })
    await asyncio.sleep(0.05)

    # Step 2: Rewrite query
    yield _sse("step", {
        "type": "rewriting",
        "title": "Optimizing search",
        "description": "Creating an optimized search query...",
    })

    query = await asyncio.to_thread(rewrite_query, question, llm)

    # Step 3: Search
    yield _sse("step", {
        "type": "searching",
        "title": "Searching documents",
        "description": f"Searching for: {query[:50]}...",
        "details": {"query": query},
    })

    docs = await asyncio.to_thread(retrieve, query, store, settings.top_k)

    # Step 4: Grade
    yield _sse("step", {
        "type": "grading",
        "title": "Evaluating results",
        "description": f"Checking relevance of {len(docs)} documents...",
        "details": {"count": len(docs)},
    })

    docs = await asyncio.to_thread(grade, question, docs, llm)

    # Emit sources
    sources = []
    for doc in docs[:5]:
        source_path = doc.metadata.get("source", "unknown")
        # Use page_label (1-indexed, human-readable) if available, otherwise fall back to page
        page_number = doc.metadata.get("page_label")
        if page_number is not None:
            # page_label might be a string like "1", convert to int
            try:
                page_number = int(page_number)
            except (ValueError, TypeError):
                page_number = doc.metadata.get("page")
        else:
            # Fall back to 0-indexed page and convert to 1-indexed
            raw_page = doc.metadata.get("page")
            page_number = (raw_page + 1) if raw_page is not None else None

        # Get similarity score (0-1 range, convert to percentage)
        similarity_score = doc.metadata.get("similarity_score")
        score_percent = round(similarity_score * 100, 1) if similarity_score is not None else None

        sources.append({
            "file_name": Path(source_path).name,
            "page": page_number,
            "chunk": doc.metadata.get("chunk_index"),
            "snippet": doc.page_content[:200],
            "score": score_percent,
            "metadata": doc.metadata,
        })

    if sources:
        yield _sse("sources", {"sources": sources})

    # Step 5: Generate with streaming
    yield _sse("step", {
        "type": "generating",
        "title": "Generating answer",
        "description": f"Synthesizing from {len(docs)} sources...",
    })

    full_answer = ""

    if llm is not None and hasattr(llm, "stream"):
        # Stream tokens using a thread to avoid blocking the event loop
        import queue
        import threading

        q: queue.Queue = queue.Queue()

        def stream_in_thread():
            try:
                for token in generate_stream(question, docs, llm):
                    q.put(("token", token))
                q.put(("done", None))
            except Exception as e:
                q.put(("error", str(e)))

        thread = threading.Thread(target=stream_in_thread, daemon=True)
        thread.start()

        while True:
            try:
                item = await asyncio.to_thread(q.get, timeout=60.0)
            except Exception:
                break

            event_type, data = item
            if event_type == "done":
                break
            elif event_type == "error":
                yield _sse("error", {"message": data})
                return
            elif event_type == "token":
                full_answer += data
                yield _sse("token", {"token": data})
    else:
        # Non-streaming fallback
        from backend.querying.nodes import generate

        full_answer = await asyncio.to_thread(generate, question, docs, llm)
        # Simulate streaming by chunking
        for i in range(0, len(full_answer), 4):
            yield _sse("token", {"token": full_answer[i:i+4]})
            await asyncio.sleep(0.01)

    yield _sse("complete", {"answer": full_answer})


async def stream_chat(
    message: str,
    settings: Settings,
) -> AsyncIterator[str]:
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
        yield _sse("error", {"message": "LLM not configured. Set OPENAI_API_KEY."})
        return

    yield _sse("step", {
        "type": "generating",
        "title": "Thinking",
        "description": "Processing your message...",
    })

    # Create simple message list
    lc_messages = [HumanMessage(content=message)]

    full_answer = ""

    try:
        if hasattr(llm, "stream"):
            # Use asyncio.to_thread for each chunk to avoid blocking
            import queue
            import threading

            q: queue.Queue = queue.Queue()

            def stream_in_thread():
                try:
                    for chunk in llm.stream(lc_messages):
                        token = getattr(chunk, "content", None)
                        if token:
                            q.put(("token", token))
                    q.put(("done", None))
                except Exception as e:
                    q.put(("error", str(e)))

            thread = threading.Thread(target=stream_in_thread, daemon=True)
            thread.start()

            while True:
                # Poll the queue with a timeout to avoid blocking forever
                try:
                    item = await asyncio.to_thread(q.get, timeout=30.0)
                except Exception:
                    break

                event_type, data = item
                if event_type == "done":
                    break
                elif event_type == "error":
                    yield _sse("error", {"message": data})
                    return
                elif event_type == "token":
                    full_answer += data
                    yield _sse("token", {"token": data})
        else:
            # Non-streaming fallback
            response = await asyncio.to_thread(llm.invoke, lc_messages)
            full_answer = str(getattr(response, "content", response))
            for i in range(0, len(full_answer), 4):
                yield _sse("token", {"token": full_answer[i:i+4]})
                await asyncio.sleep(0.01)

        yield _sse("complete", {"answer": full_answer})

    except Exception as e:
        yield _sse("error", {"message": str(e)})


__all__ = ["stream_query", "stream_chat"]
