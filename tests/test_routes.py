"""In-process HTTP API boundary regressions."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from langchain_core.documents import Document
from pydantic import SecretStr


async def create_kb(
    client: httpx.AsyncClient, text: bytes = b"offline knowledge"
) -> dict[str, Any]:
    response = await client.post(
        "/api/kb",
        data={"name": "Offline KB", "embedding_model": "offline-embedding"},
        files=[("files", ("notes.txt", text, "text/plain"))],
    )
    assert response.status_code == 200, response.text
    return response.json()


def event_names(body: str) -> list[str]:
    return [
        line.removeprefix("event: ") for line in body.splitlines() if line.startswith("event: ")
    ]


@pytest.mark.asyncio
async def test_root_health_and_model_configuration_are_safe(
    app_client: httpx.AsyncClient,
) -> None:
    root = await app_client.get("/")
    health = await app_client.get("/api/health")
    model = await app_client.get("/api/models/config")

    assert root.status_code == 200
    assert root.json() == {"message": "Agentic RAG API", "docs": "/docs"}
    assert health.json() == {"status": "ok"}
    assert model.json() == {
        "model": "gpt-4o-mini",
        "base_url": None,
        "has_api_key": False,
    }


@pytest.mark.asyncio
async def test_model_configuration_reports_but_never_returns_secret(
    app_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import backend.routes as routes

    secret = "test-only-provider-secret"
    configured = routes._settings.model_copy(update={"openai_api_key": SecretStr(secret)})
    monkeypatch.setattr(routes, "_settings", configured)

    response = await app_client.get("/api/models/config")

    assert response.status_code == 200
    assert response.json()["has_api_key"] is True
    assert secret not in response.text
    assert "openai_api_key" not in response.json()


@pytest.mark.asyncio
async def test_kb_upload_list_detail_and_query_round_trip(
    app_client: httpx.AsyncClient,
) -> None:
    created = await create_kb(app_client, b"the offline answer is forty-two")

    listed = await app_client.get("/api/kb")
    detail = await app_client.get(f"/api/kb/{created['id']}")
    query = await app_client.post(
        f"/api/kb/{created['id']}/query",
        json={"question": "What is the offline answer?"},
    )

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created["id"]]
    assert detail.status_code == 200
    assert detail.json()["documents"][0]["name"] == "notes.txt"
    assert query.status_code == 200
    assert "notes.txt" in query.json()["answer"]
    assert query.json()["sources"][0]["file_name"] == "notes.txt"


@pytest.mark.parametrize("suffix", ["", "/query", "/query/stream"])
@pytest.mark.asyncio
async def test_missing_kb_returns_404(app_client: httpx.AsyncClient, suffix: str) -> None:
    path = f"/api/kb/kb_missing{suffix}"
    response = (
        await app_client.get(path)
        if not suffix
        else await app_client.post(path, json={"question": "anything"})
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Knowledge base not found"}


@pytest.mark.asyncio
async def test_chat_without_llm_returns_documented_response(
    app_client: httpx.AsyncClient,
) -> None:
    response = await app_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "LLM not configured. Set OPENAI_API_KEY or use a model override."
    }


@pytest.mark.asyncio
async def test_query_stream_has_sse_headers_and_complete_event(
    app_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import backend.querying.stream as stream_module

    async def no_sleep(delay: float) -> None:
        del delay

    monkeypatch.setattr(stream_module.asyncio, "sleep", no_sleep)
    created = await create_kb(app_client, b"brief evidence")

    response = await app_client.post(
        f"/api/kb/{created['id']}/query/stream",
        json={"question": "evidence?"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    names = event_names(response.text)
    assert "sources" in names
    assert "token" in names
    assert names[-1] == "complete"


def test_source_conversion_handles_labels_fallbacks_scores_and_snippets(tmp_path) -> None:
    from backend.routes import _build_sources

    long_text = "x" * 250
    docs = [
        Document(
            page_content=long_text,
            metadata={
                "source": str(tmp_path / "labelled.pdf"),
                "page_label": "12",
                "page": 2,
                "chunk_index": 4,
                "similarity_score": 0.9876,
            },
        ),
        Document(
            page_content="fallback",
            metadata={
                "source": str(tmp_path / "fallback.pdf"),
                "page_label": "appendix",
                "page": 3,
            },
        ),
        Document(
            page_content="zero based",
            metadata={"source": str(tmp_path / "zero.pdf"), "page": 0},
        ),
    ]

    sources = _build_sources(docs)

    assert sources[0].file_name == "labelled.pdf"
    assert sources[0].page == 12
    assert sources[0].chunk == 4
    assert sources[0].score == 98.8
    assert sources[0].snippet == "x" * 200
    assert sources[1].page == 3
    assert sources[2].page == 1
    assert json.loads(sources[0].model_dump_json())["metadata"] == docs[0].metadata
