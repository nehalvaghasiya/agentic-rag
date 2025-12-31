"""FastAPI routes for the RAG API.

Thin layer that wires HTTP endpoints to business logic.
All request/response validation uses Pydantic models from backend.models.
"""

import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from backend.config import Settings, get_settings
from backend.models import (
    ChatStreamRequest,
    ChatResponse,
    HealthResponse,
    KnowledgeBase,
    ModelConfig,
    ModelConfigResponse,
    QueryRequest,
    QueryResponse,
    Source,
)
from backend.querying import stream_chat, stream_query
from backend.storage import KBStore

router = APIRouter()

# Initialize KB store with settings
_settings = get_settings()
_kb_store = KBStore(Path(_settings.data_dir))


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


def _build_sources(docs: list) -> list[Source]:
    """Convert retrieved documents into API source objects.

    Args:
        docs: LangChain Document-like objects.

    Returns:
        List of Source objects.
    """
    sources: list[Source] = []
    for doc in docs[:5]:
        source_path = doc.metadata.get("source", "unknown")

        page_number = doc.metadata.get("page_label")
        if page_number is not None:
            try:
                page_number = int(page_number)
            except (ValueError, TypeError):
                page_number = doc.metadata.get("page")
        else:
            raw_page = doc.metadata.get("page")
            page_number = (raw_page + 1) if raw_page is not None else None

        similarity_score = doc.metadata.get("similarity_score")
        score_percent = round(similarity_score * 100, 1) if similarity_score is not None else None

        sources.append(
            Source(
                file_name=Path(source_path).name,
                page=page_number,
                chunk=doc.metadata.get("chunk_index"),
                snippet=str(doc.page_content)[:200],
                score=score_percent,
                metadata=dict(doc.metadata),
            )
        )

    return sources


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse()


@router.get("/models/config", response_model=ModelConfigResponse)
async def get_model_config() -> ModelConfigResponse:
    """Get current model configuration (without exposing API key)."""
    return ModelConfigResponse(
        model=_settings.openai_model,
        base_url=_settings.openai_base_url,
        has_api_key=_settings.openai_api_key is not None,
    )


@router.get("/kb", response_model=list[KnowledgeBase])
async def list_knowledge_bases() -> list[KnowledgeBase]:
    """List all knowledge bases."""
    return _kb_store.list_all()


@router.post("/kb", response_model=KnowledgeBase)
async def create_knowledge_base(
    name: Annotated[str, Form()],
    embedding_model: Annotated[str, Form()],
    files: Annotated[list[UploadFile], File()],
) -> KnowledgeBase:
    """Create a new knowledge base with uploaded files.

    This endpoint accepts multipart form data with:
    - name: Knowledge base name
    - embedding_model: Model to use for embeddings
    - files: One or more files to index
    """
    return await _kb_store.create(name, embedding_model, files, _settings)


@router.get("/kb/{kb_id}")
async def get_knowledge_base(kb_id: str) -> KnowledgeBase:
    """Get details for a specific knowledge base."""
    if not _kb_store.exists(kb_id):
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    kbs = _kb_store.list_all()
    for kb in kbs:
        if kb.id == kb_id:
            return kb
    raise HTTPException(status_code=404, detail="Knowledge base not found")


@router.post("/kb/{kb_id}/query/stream")
async def query_knowledge_base_stream(kb_id: str, req: QueryRequest) -> StreamingResponse:
    """Query a knowledge base with streaming response.

    Returns Server-Sent Events (SSE) with:
    - step: Reasoning step updates
    - sources: Retrieved source documents
    - token: Streaming answer tokens
    - complete: Final complete event

    Accepts optional model_config_override to use custom LLM settings.
    """
    result = _kb_store.load(kb_id, _settings)
    if result is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    manifest, store = result

    # Apply model config override if provided
    effective_settings = _apply_model_override(_settings, req.model_config_override)

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
async def query_knowledge_base(kb_id: str, req: QueryRequest) -> QueryResponse:
    """Query a knowledge base (non-streaming).

    This endpoint exists as a fallback for environments that don't support SSE
    streaming (for example, embedded webviews).
    """
    result = _kb_store.load(kb_id, _settings)
    if result is None:
        raise HTTPException(status_code=404, detail="Knowledge base not found")

    _, store = result
    effective_settings = _apply_model_override(_settings, req.model_config_override)

    from backend.llm import get_llm
    from backend.querying.nodes import generate, grade, retrieve, rewrite_query

    llm = get_llm(effective_settings)

    query = await asyncio.to_thread(rewrite_query, req.question, llm)
    docs = await asyncio.to_thread(retrieve, query, store, effective_settings.top_k)
    docs = await asyncio.to_thread(grade, req.question, docs, llm)

    sources = _build_sources(docs)
    answer = await asyncio.to_thread(generate, req.question, docs, llm)

    return QueryResponse(answer=answer, sources=sources)


@router.post("/chat/stream")
async def chat_stream(req: ChatStreamRequest) -> StreamingResponse:
    """Direct chat without knowledge base (streaming).

    Returns Server-Sent Events (SSE) with:
    - step: Reasoning step updates
    - token: Streaming answer tokens
    - complete: Final complete event

    Accepts optional model_config_override to use custom LLM settings.
    """
    # Convert to simple message string (use last user message)
    last_user = next(
        (m.content for m in reversed(req.messages) if m.role == "user"),
        "",
    )

    # Apply model config override if provided
    effective_settings = _apply_model_override(_settings, req.model_config_override)

    return StreamingResponse(
        stream_chat(last_user, effective_settings),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatStreamRequest) -> ChatResponse:
    """General chat (non-streaming).

    This endpoint exists as a fallback for environments that don't support SSE
    streaming.
    """
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    from backend.llm import get_llm

    effective_settings = _apply_model_override(_settings, req.model_config_override)
    llm = get_llm(effective_settings)

    if llm is None:
        return ChatResponse(answer="LLM not configured. Set OPENAI_API_KEY or use a model override.")

    lc_messages = []
    for m in req.messages:
        role = (m.role or "").lower()
        if role == "system":
            lc_messages.append(SystemMessage(content=m.content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=m.content))
        else:
            lc_messages.append(HumanMessage(content=m.content))

    response = await asyncio.to_thread(llm.invoke, lc_messages)
    answer = str(getattr(response, "content", response))
    return ChatResponse(answer=answer)


__all__ = ["router"]
