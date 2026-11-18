"""Action domain model."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Action:
    tool: str
    arguments: dict[str, object] = field(default_factory=dict)
    reason: str = ""
