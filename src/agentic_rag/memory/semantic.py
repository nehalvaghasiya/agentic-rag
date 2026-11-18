"""Consented, expiring user-specific memory store; no cross-user sharing."""

import time
from dataclasses import asdict
from uuid import uuid4

from agentic_rag.data.fake import FakeStore
from agentic_rag.memory.consent import MemoryConsent
from agentic_rag.models.memory import Memory
from agentic_rag.models.principal import Principal


class SemanticMemory:
    def __init__(self, store: FakeStore) -> None:
        self.store = store
        self.consent = MemoryConsent(store)

    def remember(self, principal: Principal, text: str, ttl: int = 604800) -> Memory:
        if not self.consent.allowed(principal):
            raise PermissionError("Memory consent is disabled")
        if not 0 < len(text) <= 500 or ttl <= 0:
            raise ValueError("Invalid memory")
        now = time.time()
        memory = Memory(uuid4().hex, principal.tenant_id, principal.user_id, text, now, now + ttl)
        self.store.memories[memory.id] = asdict(memory)
        return memory

    def recall(self, principal: Principal) -> list[Memory]:
        if not self.consent.allowed(principal):
            return []
        now = time.time()
        return [
            Memory(**data)
            for data in self.store.memories.values()
            if data["tenant_id"] == principal.tenant_id
            and data["user_id"] == principal.user_id
            and (data["expires_at"] is None or data["expires_at"] > now)
        ]

    def forget(self, principal: Principal, memory_id: str) -> None:
        memory = self.store.memories.get(memory_id)
        if (
            not memory
            or memory["tenant_id"] != principal.tenant_id
            or memory["user_id"] != principal.user_id
        ):
            raise PermissionError("Memory unavailable")
        del self.store.memories[memory_id]
