"""Principal domain model."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: str
    tenant_id: str
    roles: frozenset[str] = field(default_factory=frozenset)
    groups: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.user_id or not self.tenant_id:
            raise ValueError("Principal must be authenticated with a tenant")
