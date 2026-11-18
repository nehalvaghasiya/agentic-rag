"""Query domain model."""

from dataclasses import dataclass, field

from .principal import Principal


@dataclass(frozen=True, slots=True)
class Query:
    text: str
    kb_ids: tuple[str, ...]
    principal: Principal
    session_id: str | None = None
    filters: dict[str, str] = field(default_factory=dict)
    history: tuple[dict[str, str], ...] = ()
