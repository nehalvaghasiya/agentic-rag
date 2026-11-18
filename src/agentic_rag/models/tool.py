"""Tool domain model."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, object]
    scopes: frozenset[str] = field(default_factory=frozenset)
    risk: str = "read"
    version: str = "1.0"
