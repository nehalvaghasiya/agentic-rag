"""Query-node and SSE-streaming regressions."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, cast

import pytest
from langchain_core.documents import Document

import backend.querying.stream as stream_module
from backend.config import Settings
from backend.models import KBManifest
from backend.querying.nodes import generate, generate_stream, grade, retrieve, rewrite_query
from backend.querying.stream import stream_chat, stream_query
from backend.storage import VectorStore
from tests.support import ScriptedLLM


class RecordingStore:
    def __init__(self, docs: list[Document]) -> None:
        self.docs = docs
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, k: int = 5) -> list[Document]:
        self.calls.append((query, k))
        return self.docs[:k]


def decode_sse(frame: str) -> tuple[str, dict[str, Any]]:
    lines = frame.rstrip().splitlines()
    assert lines[0].startswith("event: ")
    assert lines[1].startswith("data: ")
    return lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))


async def collect_events(events: AsyncIterator[str]) -> list[tuple[str, dict[str, Any]]]:
    return [decode_sse(frame) async for frame in events]


async def no_sleep(delay: float) -> None:
    del delay


def manifest() -> KBManifest:
    return KBManifest(
        id="kb_test",
        name="Test",
        embedding_model="offline",
        created_at=datetime(2026, 9, 20),
    )


def test_rewrite_query_uses_scripted_response_and_records_prompt() -> None:
    llm = ScriptedLLM(invoke=["concise search"])

    result = rewrite_query("A longer question?", llm)

    assert result == "concise search"
    assert len(llm.invoke_calls) == 1
    assert "A longer question?" in llm.invoke_calls[0]


@pytest.mark.parametrize("result", ["", "   ", RuntimeError("provider failed")])
def test_rewrite_query_falls_back_to_original_question(result: str | Exception) -> None:
    llm = ScriptedLLM(invoke=[result])

    assert rewrite_query("original", llm) == "original"


def test_retrieve_forwards_query_and_limit() -> None:
    docs = [Document(page_content="one"), Document(page_content="two")]
    store = RecordingStore(docs)

    assert retrieve("search terms", cast(VectorStore, store), k=1) == docs[:1]
    assert store.calls == [("search terms", 1)]


def test_grade_uses_scripted_decisions_and_contains_provider_errors() -> None:
    docs = [
        Document(page_content="relevant"),
        Document(page_content="irrelevant"),
        Document(page_content="provider error"),
    ]
    llm = ScriptedLLM(invoke=["yes", "no", RuntimeError("unavailable")])

    result = grade("question", docs, llm)

    assert result == [docs[0], docs[2]]
    assert len(llm.invoke_calls) == 3


def test_generate_has_deterministic_no_document_and_no_llm_fallbacks() -> None:
    assert "couldn't find relevant information" in generate("question", [], None)

    docs = [Document(page_content="known fact", metadata={"source": "facts.txt"})]
    answer = generate("question", docs, None)
    assert answer == "Here are the relevant excerpts:\n\n[1] facts.txt: known fact..."


def test_generate_and_generate_stream_use_scripted_provider() -> None:
    docs = [Document(page_content="known fact", metadata={"source": "facts.txt"})]
    invoke_llm = ScriptedLLM(invoke=["final answer"])
    stream_llm = ScriptedLLM(stream=["final ", "answer"])

    assert generate("question", docs, invoke_llm) == "final answer"
    assert list(generate_stream("question", docs, stream_llm)) == ["final ", "answer"]
    assert "known fact" in invoke_llm.invoke_calls[0]
    assert "known fact" in stream_llm.stream_calls[0]


def test_generate_stream_contains_provider_exception() -> None:
    docs = [Document(page_content="known fact", metadata={"source": "facts.txt"})]
    llm = ScriptedLLM(stream=[RuntimeError("provider unavailable")])

    assert list(generate_stream("question", docs, llm)) == [
        "Error generating answer: provider unavailable"
    ]


@pytest.mark.asyncio
async def test_query_stream_emits_valid_ordered_events_and_source_metadata(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    monkeypatch.setattr(stream_module.asyncio, "sleep", no_sleep)
    docs = [
        Document(
            page_content="first excerpt",
            metadata={
                "source": "/tmp/first.pdf",
                "page_label": "7",
                "chunk_index": 2,
                "similarity_score": 0.876,
            },
        ),
        Document(
            page_content="second excerpt",
            metadata={
                "source": "/tmp/second.pdf",
                "page": 0,
                "chunk_index": 0,
                "similarity_score": 0.5,
            },
        ),
    ]
    store = RecordingStore(docs)

    events = await collect_events(
        stream_query("question", (manifest(), cast(VectorStore, store)), settings)
    )

    event_names = [name for name, _ in events]
    assert event_names[:4] == ["step", "step", "step", "step"]
    assert event_names[4:6] == ["sources", "step"]
    assert event_names[-1] == "complete"
    assert "error" not in event_names
    sources = events[4][1]["sources"]
    assert sources[0] == {
        "file_name": "first.pdf",
        "page": 7,
        "chunk": 2,
        "snippet": "first excerpt",
        "score": 87.6,
        "metadata": docs[0].metadata,
    }
    assert sources[1]["page"] == 1
    tokens = "".join(data["token"] for name, data in events if name == "token")
    assert events[-1][1]["answer"] == tokens
    assert store.calls == [("question", settings.top_k)]


@pytest.mark.asyncio
async def test_query_stream_provider_failure_emits_error_without_completion(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    import backend.llm as llm_module

    monkeypatch.setattr(stream_module.asyncio, "sleep", no_sleep)
    llm = ScriptedLLM(
        invoke=["rewritten", "yes"],
    )
    monkeypatch.setattr(llm_module, "get_llm", lambda current_settings: llm)

    def failing_provider_stream(question, docs, current_llm):
        del question, docs, current_llm
        yield "partial"
        raise RuntimeError("stream failed")

    monkeypatch.setattr(stream_module, "generate_stream", failing_provider_stream)
    store = RecordingStore([Document(page_content="context", metadata={"source": "source.txt"})])

    events = await collect_events(
        stream_query("question", (manifest(), cast(VectorStore, store)), settings)
    )

    event_names = [name for name, _ in events]
    assert event_names[-1] == "error"
    assert "complete" not in event_names
    assert events[-1][1] == {"message": "stream failed"}


@pytest.mark.asyncio
async def test_chat_stream_without_llm_emits_configuration_error(settings: Settings) -> None:
    events = await collect_events(stream_chat("hello", settings))

    assert events == [("error", {"message": "LLM not configured. Set OPENAI_API_KEY."})]
