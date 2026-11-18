"""Memory domain model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Memory:
    id: str
    tenant_id: str
    user_id: str
    text: str
    created_at: float
    expires_at: float | None = None
    source: str = "user"
