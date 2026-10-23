"""FastAPI routes for the RAG API.

Thin layer that wires HTTP endpoints to business logic.
All request/response validation uses Pydantic models from backend.models.
"""

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from backend.config import Settings
from backend.dependencies import KBStoreDep, ServicesDep, SettingsDep
from backend.errors import ApplicationError, stage_context
from backend.models import (
    ChatRequest,
    ChatResponse,
    ErrorCode,
    HealthResponse,
    KnowledgeBase,
    ModelConfig,
    ModelConfigResponse,
    QueryRequest,
    QueryResponse,
)
from backend.prompts import build_chat_messages
from backend.querying import stream_chat, stream_query
from backend.request_validation import BoundedJSONRoute
from backend.sources import build_sources

router = APIRouter(route_class=BoundedJSONRoute)
SSE_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "description": (
            "SSE connection opened. A terminal complete event indicates success; a terminal "
            "error event carries ErrorEnvelope. No complete event follows an error."
        ),
        "content": {"text/event-stream": {"schema": {"type": "string"}}},
    }
}


def _apply_model_override(base_settings: Settings, override: ModelConfig | None) -> Settings:
    """Create a new Settings instance with model config overrides applied.

    Args:
        base_settings: Base settings from environment.
        override: Optional model config override from request.

    Returns:
        Settings instance with overrides applied.
    """
    if override is None:
        return base_settings

    from pydantic import SecretStr

    # Create a copy of settings with overrides
    overrides = {}
    if override.api_key:
        overrides["openai_api_key"] = SecretStr(override.api_key)
    if override.model:
        overrides["openai_model"] = override.model
    if override.base_url:
        overrides["openai_base_url"] = override.base_url

    if not overrides:
        return base_settings

    # Create new settings with overrides
    return base_settings.model_copy(update=overrides)


@router.get("/health", response_model=HealthResponse)
async def health_check(services: ServicesDep) -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse()


@router.get("/models/config", response_model=ModelConfigResponse)
async def get_model_config(settings: SettingsDep) -> ModelConfigResponse:
    """Get current model configuration (without exposing API key)."""
    return ModelConfigResponse(
        model=settings.openai_model,
        base_url=settings.openai_base_url,
        has_api_key=settings.openai_api_key is not None,
    )


@router.get("/kb", response_model=list[KnowledgeBase])
async def list_knowledge_bases(kb_store: KBStoreDep) -> list[KnowledgeBase]:
    """List all knowledge bases."""
    return kb_store.list_all()


@router.post("/kb", response_model=KnowledgeBase)
async def create_knowledge_base(
    name: Annotated[str, Form()],
    embedding_model: Annotated[str, Form()],
    files: Annotated[list[UploadFile], File()],
    settings: SettingsDep,
    kb_store: KBStoreDep,
) -> KnowledgeBase:
    """Create a new knowledge base with uploaded files.

    This endpoint accepts multipart form data with:
    - name: Knowledge base name
    - embedding_model: Model to use for embeddings
    - files: One or more files to index
    """
    return await kb_store.create(name, embedding_model, files, settings)


@router.get("/kb/{kb_id}")
async def get_knowledge_base(kb_id: str, kb_store: KBStoreDep) -> KnowledgeBase:
    """Get details for a specific knowledge base."""
    if not kb_store.exists(kb_id):
        raise ApplicationError(ErrorCode.NOT_FOUND)
    kbs = kb_store.list_all()
    for kb in kbs:
        if kb.id == kb_id:
            return kb
    raise ApplicationError(ErrorCode.NOT_FOUND)


@router.post("/kb/{kb_id}/query/stream", response_class=StreamingResponse, responses=SSE_RESPONSES)
async def query_knowledge_base_stream(
    kb_id: str, req: QueryRequest, settings: SettingsDep, kb_store: KBStoreDep
) -> StreamingResponse:
    """Query a knowledge base with streaming response.

    Returns Server-Sent Events (SSE) with:
    - step: Reasoning step updates
    - sources: Retrieved source documents
    - token: Streaming answer tokens
    - complete: Final complete event
    - error: Terminal ErrorEnvelope with the response's X-Correlation-ID

    Accepts optional model_config_override to use custom LLM settings.
    """
    result = kb_store.load(kb_id, settings)
    if result is None:
        raise ApplicationError(ErrorCode.NOT_FOUND)

    manifest, store = result

    # Apply model config override if provided
    effective_settings = _apply_model_override(settings, req.model_config_override)

    return StreamingResponse(
        stream_query(req.question, (manifest, store), effective_settings),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/kb/{kb_id}/query", response_model=QueryResponse)
async def query_knowledge_base(
    kb_id: str, req: QueryRequest, settings: SettingsDep, kb_store: KBStoreDep
) -> QueryResponse:
    """Query a knowledge base (non-streaming).

    This endpoint exists as a fallback for environments that don't support SSE
    streaming (for example, embedded webviews).
    """
    result = kb_store.load(kb_id, settings)
    if result is None:
        raise ApplicationError(ErrorCode.NOT_FOUND)

    _, store = result
    effective_settings = _apply_model_override(settings, req.model_config_override)

    from backend.llm import get_llm
    from backend.querying.nodes import generate, grade, retrieve, rewrite_query

    stage_context.set("query.initialize")
    llm = get_llm(effective_settings)

    stage_context.set("query.rewrite")
    query = await asyncio.to_thread(rewrite_query, req.question, llm)
    stage_context.set("query.retrieve")
    docs = await asyncio.to_thread(retrieve, query, store, effective_settings.top_k)
    stage_context.set("query.grade")
    docs = await asyncio.to_thread(grade, req.question, docs, llm)

    stage_context.set("query.sources")
    sources = build_sources(docs)
    stage_context.set("query.generate")
    answer = await asyncio.to_thread(generate, req.question, docs, llm)

    return QueryResponse(answer=answer, sources=sources)


@router.post("/chat/stream", response_class=StreamingResponse, responses=SSE_RESPONSES)
async def chat_stream(req: ChatRequest, settings: SettingsDep) -> StreamingResponse:
    """Direct chat without knowledge base (streaming).

    Returns Server-Sent Events (SSE) with:
    - step: Reasoning step updates
    - token: Streaming answer tokens
    - complete: Final complete event
    - error: Terminal ErrorEnvelope with the response's X-Correlation-ID

    Accepts optional model_config_override to use custom LLM settings.
    """
    # Apply model config override if provided
    effective_settings = _apply_model_override(settings, req.model_config_override)

    return StreamingResponse(
        stream_chat(req.messages, effective_settings),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, settings: SettingsDep) -> ChatResponse:
    """General chat (non-streaming).

    This endpoint exists as a fallback for environments that don't support SSE
    streaming.
    """
    from backend.llm import get_llm

    effective_settings = _apply_model_override(settings, req.model_config_override)
    stage_context.set("chat.initialize")
    llm = get_llm(effective_settings)

    if llm is None:
        raise ApplicationError(ErrorCode.MODEL_NOT_CONFIGURED)

    lc_messages = build_chat_messages(req.messages)

    stage_context.set("chat.generate")
    response = await asyncio.to_thread(llm.invoke, lc_messages)
    answer = str(getattr(response, "content", response))
    return ChatResponse(answer=answer)


__all__ = ["router"]
