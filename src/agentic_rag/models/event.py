"""Event domain model."""

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class Event:
    id: int
    run_id: str
    type: str
    data: dict[str, object]
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
