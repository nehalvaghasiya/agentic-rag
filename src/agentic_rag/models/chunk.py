"""Chunk domain model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Chunk:
    id: str
    document_id: str
    kb_id: str
    tenant_id: str
    version: int
    text: str
    ordinal: int
    page: int | None = None
    section: str | None = None
    parent_id: str | None = None
