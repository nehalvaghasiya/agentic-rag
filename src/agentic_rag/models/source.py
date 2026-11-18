"""Source domain model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    tenant_id: str
    uri: str
    kind: str
    trust: str = "internal"
