"""Document domain model."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class Document:
    id: str
    kb_id: str
    tenant_id: str
    title: str
    content_type: str
    version: int = 1
    status: str = "processing"
    owner: str = ""
    groups: frozenset[str] = field(default_factory=frozenset)
    source_uri: str | None = None
    size: int = 0
    acl_version: int = 1
    created_at: str = ""
    updated_at: str = ""
