"""Upload domain model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Upload:
    filename: str
    content: bytes
    content_type: str | None = None
