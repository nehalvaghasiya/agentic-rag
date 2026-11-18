"""Tenant/group/owner ACL enforcement independent of LLM instructions."""

from agentic_rag.data.fake import FakeStore
from agentic_rag.models.document import Document
from agentic_rag.models.principal import Principal


class AccessControl:
    def __init__(self, store: FakeStore) -> None:
        self.store = store

    def can_read(self, doc: Document, principal: Principal) -> bool:
        return self.store.allowed(doc, principal)

    def assert_write(self, doc: Document, principal: Principal) -> None:
        if not self.store.allowed(doc, principal) or (
            doc.owner != principal.user_id and "admin" not in principal.roles
        ):
            raise PermissionError("Write access denied")
