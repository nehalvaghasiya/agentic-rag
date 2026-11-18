"""Result domain model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolResult:
    name: str
    status: str
    output: dict[str, object]
    evidence_ids: tuple[str, ...] = ()
    error: str | None = None
    duration_ms: float = 0.0
