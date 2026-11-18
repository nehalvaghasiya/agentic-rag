"""Optional explicit memory API. Chat never automatically recalls cross-chat facts."""

import time
from typing import Any
from uuid import uuid4

from agentic_rag.data.repository import Repository
from agentic_rag.models.principal import Principal


class PrivateMemory:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    async def consent(self, p: Principal, enabled: bool) -> None:
        await self.repo.state_put("consent", "memory", {"enabled": enabled}, p)
        if not enabled:
            for memory in await self.repo.state_list("memory", p):
                await self.repo.state_delete("memory", memory["id"], p)

    async def recall(self, p: Principal) -> list[dict[str, Any]]:
        consent = await self.repo.state_get("consent", "memory", p)
        if not consent or not consent["enabled"]:
            return []
        return [m for m in await self.repo.state_list("memory", p) if m["expires_at"] > time.time()]

    async def remember(self, p: Principal, text: str, ttl: int = 604800) -> dict[str, Any]:
        consent = await self.repo.state_get("consent", "memory", p)
        if not consent or not consent["enabled"]:
            raise PermissionError("Memory consent is disabled")
        if not 0 < len(text) <= 500 or ttl <= 0:
            raise ValueError("Invalid memory")
        memory: dict[str, Any] = {"id": uuid4().hex, "text": text, "expires_at": time.time() + ttl}
        await self.repo.state_put("memory", memory["id"], memory, p)
        return memory

    async def forget(self, p: Principal, uid: str) -> None:
        if not await self.repo.state_get("memory", uid, p):
            raise PermissionError("Memory unavailable")
        await self.repo.state_delete("memory", uid, p)
