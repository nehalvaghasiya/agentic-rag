"""Explicit opt-in policy for persistent semantic memories."""

from agentic_rag.data.fake import FakeStore
from agentic_rag.models.principal import Principal


class MemoryConsent:
    def __init__(self, store: FakeStore) -> None:
        self.store = store

    def allowed(self, principal: Principal) -> bool:
        return (principal.tenant_id, principal.user_id) in self.store.consent

    def grant(self, principal: Principal) -> None:
        self.store.consent.add((principal.tenant_id, principal.user_id))

    def revoke(self, principal: Principal) -> None:
        self.store.consent.discard((principal.tenant_id, principal.user_id))
        for uid in [
            k
            for k, v in self.store.memories.items()
            if v["tenant_id"] == principal.tenant_id and v["user_id"] == principal.user_id
        ]:
            self.store.memories.pop(uid, None)
