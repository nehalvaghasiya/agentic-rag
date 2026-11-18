"""Authorized lexical retrieval: PostgreSQL FTS or deterministic test search."""

import re

from agentic_rag.data.repository import Repository
from agentic_rag.models.evidence import Evidence
from agentic_rag.models.query import Query


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.casefold())


class KeywordSearch:
    def __init__(self, store: Repository) -> None:
        self.store = store

    async def search(self, query: Query, limit: int) -> list[Evidence]:
        return await self.store.keyword(query.text, query.kb_ids, query.principal, limit)
