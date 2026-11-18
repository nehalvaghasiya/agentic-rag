"""Job domain model."""

from dataclasses import dataclass


@dataclass(slots=True)
class Job:
    id: str
    tenant_id: str
    kb_id: str
    document_id: str
    status: str = "queued"
    attempts: int = 0
    error: str | None = None
    created_at: str = ""
    version: int = 1
    lease_until: float = 0.0
