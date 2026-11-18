"""Authorized search shared by fast RAG and specialist tools."""

from dataclasses import replace
from typing import Any

from agentic_rag.data.cache import Cache, fingerprint
from agentic_rag.data.repository import Repository
from agentic_rag.models.evidence import Evidence
from agentic_rag.models.principal import Principal
from agentic_rag.models.query import Query
from agentic_rag.search.dense import DenseSearch
from agentic_rag.search.hybrid import HybridSearch
from agentic_rag.search.keyword import KeywordSearch
from agentic_rag.search.rerank import Reranker


class SearchService:
    def __init__(self, store: Repository, embed: Any) -> None:
        self.store, self.cache = store, Cache(store)
        self.dense, self.keyword = DenseSearch(store, embed), KeywordSearch(store)
        self.hybrid, self.rerank = HybridSearch(self.dense, self.keyword), Reranker()

    async def search(
        self, query: Query, *, strategy: str = "hybrid", limit: int = 5
    ) -> list[Evidence]:
        if not query.text.strip() or not 1 <= limit <= 50:
            raise ValueError("Invalid search query or limit")
        if not query.kb_ids:
            return []
        revision = await self.store.revision(query.kb_ids, query.principal)
        key = "retrieval:" + fingerprint(
            [
                query.text,
                sorted(query.kb_ids),
                strategy,
                limit,
                revision,
                sorted(query.principal.groups),
                sorted(query.principal.roles),
            ]
        )
        cached = await self.cache.get(key, query.principal)
        if run_id := query.filters.get("run_id"):
            await self.store.log(
                run_id,
                "cache",
                {
                    "layer": "retrieval",
                    "status": "hit" if cached else "miss",
                    "title": "Retrieval cache",
                },
                query.principal,
            )
        if cached:
            found = await self.get(cached["ids"], query.principal)
            if {e.chunk_id for e in found} == set(cached["ids"]):
                ordered = {e.chunk_id: e for e in found}
                return [replace(ordered[cid], score=cached["scores"][cid]) for cid in cached["ids"]]
        if strategy == "dense":
            results = await self.dense.search(query, limit)
        elif strategy == "keyword":
            results = await self.keyword.search(query, limit)
        elif strategy == "hybrid":
            results = await self.hybrid.search(query, limit)
        elif strategy == "advanced":
            results = self.rerank.rank(
                query.text, await self.hybrid.search(query, limit * 2), limit
            )
        else:
            raise ValueError("Unknown search strategy")
        allowed = {
            e.chunk_id for e in await self.get([e.chunk_id for e in results], query.principal)
        }
        results = [e for e in results if e.chunk_id in allowed]
        await self.cache.put(
            key,
            {
                "ids": [e.chunk_id for e in results],
                "scores": {e.chunk_id: e.score for e in results},
            },
            query.principal,
        )
        return results

    async def get(self, ids: list[str], principal: Principal) -> list[Evidence]:
        return await self.store.evidence(ids, principal)
