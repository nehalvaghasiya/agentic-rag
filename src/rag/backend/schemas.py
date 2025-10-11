"""
Pydantic schemas for API requests and responses.

All schemas are validated at runtime for type safety.
"""

from typing import Any

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    """Response for file upload."""

    message: str
    num_documents: int
    num_chunks: int
    document_ids: list[str]
    warnings: list[str] | None = None  # System warnings (e.g., fallback mode)


class QueryRequest(BaseModel):
    """Request for RAG query."""

    query: str = Field(..., min_length=1, description="User query")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of context chunks to retrieve")


class Source(BaseModel):
    """Source document information."""

    content: str
    metadata: dict[str, Any]


class QueryResponse(BaseModel):
    """Response for RAG query."""

    answer: str
    query: str
    sources: list[Source] | None = None
    warnings: list[str] | None = None  # System warnings (e.g., fallback mode)


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    components: dict[str, str]
