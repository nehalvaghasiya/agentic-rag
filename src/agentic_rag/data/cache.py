"""Exact, principal-scoped caches. Cached sources are always reauthorized."""

import hashlib
import json
import time
from typing import Any

from agentic_rag.data.repository import Repository
from agentic_rag.models.principal import Principal


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class Cache:
    def __init__(self, repo: Repository) -> None:
        self.repo = repo

    async def get(self, key: str, p: Principal) -> dict[str, Any] | None:
        value = await self.repo.state_get("cache", key, p)
        if value and float(value.get("expires_at", 0)) > time.time():
            return value
        if value:
            await self.repo.state_delete("cache", key, p)
        return None

    async def put(self, key: str, value: dict[str, Any], p: Principal, ttl: int = 300) -> None:
        await self.repo.state_put("cache", key, {**value, "expires_at": time.time() + ttl}, p)
