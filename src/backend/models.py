"""API and internal data models.

All Pydantic models for API requests, responses, and internal data.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(StrEnum):
    """Stable public failure categories shared by HTTP and execution events."""

    BAD_REQUEST = "BAD_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    CONFLICT = "CONFLICT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    MODEL_NOT_CONFIGURED = "MODEL_NOT_CONFIGURED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    PROVIDER_AUTH_ERROR = "PROVIDER_AUTH_ERROR"
    PROVIDER_REQUEST_ERROR = "PROVIDER_REQUEST_ERROR"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    HTTP_ERROR = "HTTP_ERROR"


ValidationCode = Literal["required", "invalid_type", "invalid_json", "invalid_value"]


class ValidationIssue(BaseModel):
    """A declared field path and controlled validation explanation; never input."""

    model_config = ConfigDict(extra="forbid")
    field: str
    code: ValidationCode
    message: str


class PublicError(BaseModel):
    """Safe failure information. Retryability is advisory, not replay permission."""

    model_config = ConfigDict(extra="forbid")
    code: ErrorCode
    message: str
    retryable: bool
    correlation_id: str
    details: list[ValidationIssue] | None = Field(default=None, max_length=20)


class ErrorEnvelope(BaseModel):
    """Canonical HTTP error body and terminal SSE error data."""

    model_config = ConfigDict(extra="forbid")
    error: PublicError


class ModelConfig(BaseModel):
    """LLM model configuration for API requests."""

    api_key: str | None = Field(default=None, description="API key (overrides env)")
    model: str | None = Field(default=None, description="Model name (overrides env)")
    base_url: str | None = Field(default=None, description="API base URL (overrides env)")


class QueryRequest(BaseModel):
    """Request to query a knowledge base."""

    question: str = Field(..., description="Question to ask")
    model_config_override: ModelConfig | None = Field(
        default=None, description="Optional model config override"
    )


class ChatStreamRequest(BaseModel):
    """Request for streaming chat."""

    messages: list[ChatMessage] = Field(..., description="Chat history")
    model_config_override: ModelConfig | None = Field(
        default=None, description="Optional model config override"
    )


class ChatRequest(BaseModel):
    """Request for general chat."""

    messages: list[ChatMessage] = Field(..., description="Chat history")


class ChatMessage(BaseModel):
    """A single chat message."""

    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")


class ModelConfigResponse(BaseModel):
    """Response with current model configuration (without exposing secrets)."""

    model: str = Field(..., description="Current model name")
    base_url: str | None = Field(default=None, description="Current base URL")
    has_api_key: bool = Field(..., description="Whether API key is configured")


class Source(BaseModel):
    """A source citation from retrieved documents."""

    file_name: str = Field(..., description="Source file name")
    page: int | None = Field(default=None, description="Page number (1-indexed, for PDFs)")
    chunk: int | None = Field(default=None, description="Chunk index")
    snippet: str = Field(..., description="Text snippet from the source")
    score: float | None = Field(default=None, description="Similarity score (0-100%)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class KnowledgeBase(BaseModel):
    """Knowledge base summary for API responses."""

    id: str
    name: str
    embedding_model: str
    created_at: datetime
    file_count: int
    total_size: int
    documents: list[DocumentMeta] = Field(default_factory=list)
    chunking_strategy: str = Field(default="Recursive (800/120)")
    ranking_strategy: str = Field(default="Hybrid")
    last_modified: datetime | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"


class DocumentMeta(BaseModel):
    """Metadata for an uploaded document."""

    id: str
    name: str
    type: str
    size: int
    uploaded_at: datetime


class KBManifest(BaseModel):
    """Knowledge base manifest stored on disk."""

    id: str
    name: str
    embedding_model: str
    created_at: datetime
    documents: list[DocumentMeta] = Field(default_factory=list)


class StepEvent(BaseModel):
    """A reasoning step event."""

    type: str  # analyzing, rewriting, searching, grading, generating
    title: str
    description: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class TokenEvent(BaseModel):
    """A token streaming event."""

    token: str


class SourcesEvent(BaseModel):
    """Sources citation event."""

    sources: list[Source]


class CompleteEvent(BaseModel):
    """Completion event with final answer."""

    answer: str


class ErrorEvent(ErrorEnvelope):
    """Terminal execution failure; serialized identically to HTTP errors."""


class ChatResponse(BaseModel):
    """Non-streaming chat response."""

    answer: str = Field(..., description="Final assistant answer")


class QueryResponse(BaseModel):
    """Non-streaming query response for a knowledge base."""

    answer: str = Field(..., description="Final answer")
    sources: list[Source] = Field(default_factory=list, description="Retrieved sources")


# Fix forward reference
ChatRequest.model_rebuild()
ChatStreamRequest.model_rebuild()


__all__ = [
    "ErrorCode",
    "ValidationCode",
    "ValidationIssue",
    "PublicError",
    "ErrorEnvelope",
    # Request models
    "ModelConfig",
    "QueryRequest",
    "ChatStreamRequest",
    "ChatRequest",
    "ChatMessage",
    # Response models
    "Source",
    "KnowledgeBase",
    "HealthResponse",
    "ModelConfigResponse",
    # Internal models
    "DocumentMeta",
    "KBManifest",
    # Event models
    "StepEvent",
    "TokenEvent",
    "SourcesEvent",
    "CompleteEvent",
    "ErrorEvent",
    # Non-streaming responses
    "ChatResponse",
    "QueryResponse",
]
