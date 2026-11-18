"""Tenant/user-bound short-term conversation history (demo adapter)."""

from uuid import uuid4

from agentic_rag.data.fake import FakeStore
from agentic_rag.models.principal import Principal


class SessionMemory:
    def __init__(self, store: FakeStore) -> None:
        self.store = store

    def create(self, principal: Principal) -> dict[str, object]:
        uid = uuid4().hex
        session: dict[str, object] = {
            "id": uid,
            "tenant": principal.tenant_id,
            "user": principal.user_id,
            "messages": [],
        }
        self.store.sessions[uid] = session
        return session

    def read(self, uid: str, principal: Principal) -> dict[str, object]:
        session = self.store.sessions.get(uid)
        if (
            not session
            or session["tenant"] != principal.tenant_id
            or session["user"] != principal.user_id
        ):
            raise PermissionError("Session unavailable")
        return session

    def list(self, principal: Principal) -> list[dict[str, object]]:
        return [
            v
            for v in self.store.sessions.values()
            if v["tenant"] == principal.tenant_id and v["user"] == principal.user_id
        ]

    def clear(self, uid: str, principal: Principal) -> None:
        self.read(uid, principal)
        del self.store.sessions[uid]
