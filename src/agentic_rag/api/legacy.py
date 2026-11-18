"""Temporary backwards-compatible facade for the preserved React UI.

All retrieval/generation delegates to the same new AgentService, without the old
query-rewrite/grading path. Delete after frontend completes its v2 migration.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agentic_rag.api.deps import get_principal, get_runtime
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.models.principal import Principal
from agentic_rag.models.query import Query
from agentic_rag.models.upload import Upload

router = APIRouter(prefix="/api", tags=["Legacy compatibility"])


class LegacyQuery(BaseModel):
    question: str
    model_config_override: dict[str, object] | None = None


async def compatible_kb(
    runtime: RuntimeFactory, principal: Principal, kb: dict[str, Any]
) -> dict[str, object]:
    docs = await runtime.repo.list_docs(principal, kb["id"])
    now = datetime.now(UTC).isoformat()
    return {
        "id": kb["id"],
        "name": kb["name"],
        "embedding_model": runtime.settings.embedding_model,
        "created_at": now,
        "last_modified": now,
        "file_count": len(docs),
        "total_size": sum(doc.size for doc in docs),
        "documents": [
            {
                "id": doc.id,
                "name": doc.title,
                "type": doc.content_type or "text/plain",
                "size": doc.size,
                "uploaded_at": doc.created_at or now,
            }
            for doc in docs
        ],
        "chunking_strategy": "Token (180/30)",
        "ranking_strategy": "Hybrid (RRF)",
    }


async def source_adapter(
    runtime: RuntimeFactory, ids: tuple[str, ...], principal: Principal
) -> list[dict[str, object]]:
    return [
        {
            "file_name": ev.title,
            "page": ev.page,
            "chunk": None,
            "snippet": ev.text[:500],
            "score": None,
            "metadata": {"evidence_id": ev.chunk_id, "document_id": ev.document_id},
        }
        for ev in await runtime.repo.evidence(list(ids), principal)
    ]


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/models/config")
async def model_config(runtime: RuntimeFactory = Depends(get_runtime)) -> dict[str, object]:
    return {
        "model": runtime.settings.model,
        "base_url": None,
        "has_api_key": runtime.settings.provider == "openai",
    }


@router.get("/kb")
async def list_kbs(
    runtime: RuntimeFactory = Depends(get_runtime), principal: Principal = Depends(get_principal)
) -> list[dict[str, object]]:
    return [
        await compatible_kb(runtime, principal, kb) for kb in await runtime.repo.list_kbs(principal)
    ]


@router.post("/kb")
async def create_kb(
    name: str = Form(...),
    embedding_model: str = Form("demo"),
    files: list[UploadFile] = File(...),
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, object]:
    if not files or len(files) > 10:
        raise ValueError("1–10 files required")
    uploads = [
        Upload(f.filename or "", await f.read(8 * 1024 * 1024 + 1), f.content_type) for f in files
    ]
    # Validate all files before creating the KB (no empty orphan on rejection).
    for value in uploads:
        runtime.knowledge.parser.parse(value)
    kb = await runtime.knowledge.create_kb(name, principal)
    jobs = await runtime.knowledge.submit(uploads, kb["id"], principal)
    if runtime.settings.environment == "demo":
        for _ in jobs:
            await runtime.worker.once(principal)
    return await compatible_kb(runtime, principal, kb)


@router.get("/kb/{kb_id}")
async def get_kb(
    kb_id: str,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, object]:
    return await compatible_kb(runtime, principal, await runtime.repo.check_kb(kb_id, principal))


def check_override(req: LegacyQuery) -> None:
    if req.model_config_override and any(req.model_config_override.values()):
        raise ValueError("Client-provided model credentials are disabled; configure the server")


@router.post("/kb/{kb_id}/query")
async def query(
    kb_id: str,
    req: LegacyQuery,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, object]:
    check_override(req)
    answer = await runtime.agent.run(Query(req.question, (kb_id,), principal), mode="auto")
    return {
        "answer": answer.text,
        "sources": await source_adapter(runtime, answer.citations, principal),
    }


def frame(kind: str, value: dict[str, object]) -> str:
    return f"event: {kind}\ndata: {json.dumps(value)}\n\n"


@router.post("/kb/{kb_id}/query/stream")
async def query_stream(
    kb_id: str,
    req: LegacyQuery,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    check_override(req)
    await runtime.repo.check_kb(kb_id, principal)

    async def execute() -> AsyncIterator[str]:
        try:
            answer = await runtime.agent.run(Query(req.question, (kb_id,), principal), mode="auto")
            for event in await runtime.repo.events(answer.run_id, principal):
                if event.type in {"route", "tool_started", "retrieval", "generation"}:
                    mapping = {
                        "route": "analyzing",
                        "tool_started": "searching",
                        "retrieval": "searching",
                        "generation": "generating",
                    }
                    yield frame(
                        "step",
                        {
                            "type": mapping[event.type],
                            "title": event.type,
                            "description": str(event.data)[:120],
                            "details": {},
                        },
                    )
            sources = await source_adapter(runtime, answer.citations, principal)
            if sources:
                yield frame("sources", {"sources": sources})
            yield frame("token", {"token": answer.text})
            yield frame("complete", {"answer": answer.text})
        except Exception:
            yield frame(
                "error",
                {
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "Query failed",
                        "retryable": True,
                        "correlation_id": "a" * 32,
                    }
                },
            )

    return StreamingResponse(execute(), media_type="text/event-stream")


@router.post("/chat")
async def chat(
    req: dict[str, object],
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, str]:
    messages = req.get("messages", [])
    if not isinstance(messages, list) or not messages:
        raise ValueError("Messages required")
    content = messages[-1].get("content", "")
    if not isinstance(content, str):
        raise ValueError("Invalid content")
    if req.get("model_config_override"):
        raise ValueError("Configure model credentials on the server")
    history = tuple(
        {"role": str(m["role"]), "content": str(m["content"])}
        for m in messages[:-1]
        if isinstance(m, dict)
        and m.get("role") in {"user", "assistant"}
        and isinstance(m.get("content"), str)
    )
    answer = await runtime.agent.run(Query(content, (), principal, history=history))
    return {"answer": answer.text}


@router.post("/chat/stream")
async def chat_stream(
    req: dict[str, object],
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    result = await chat(req, runtime, principal)

    async def execute() -> AsyncIterator[str]:
        yield frame(
            "step",
            {"type": "generating", "title": "Model response", "description": "", "details": {}},
        )
        yield frame("token", {"token": result["answer"]})
        yield frame("complete", {"answer": result["answer"]})

    return StreamingResponse(execute(), media_type="text/event-stream")
