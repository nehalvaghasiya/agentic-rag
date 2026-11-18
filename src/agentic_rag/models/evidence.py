"""Evidence domain model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Evidence:
    chunk_id: str
    document_id: str
    version: int
    text: str
    score: float
    source_uri: str | None
    page: int | None
    section: str | None
    tenant_id: str
    acl_version: int
    title: str = ""

    def citation(self) -> str:
        return self.chunk_id
