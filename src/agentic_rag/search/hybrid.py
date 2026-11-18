"""Parallel dense+keyword retrieval with reciprocal rank fusion."""

import asyncio
from dataclasses import replace

from agentic_rag.models.evidence import Evidence
from agentic_rag.models.query import Query
from agentic_rag.search.dense import DenseSearch
from agentic_rag.search.keyword import KeywordSearch


class HybridSearch:
    def __init__(self, dense: DenseSearch, keyword: KeywordSearch) -> None:
        self.dense = dense
        self.keyword = keyword

    def fuse(self, lists: list[list[Evidence]], limit: int, rrf_k: int = 60) -> list[Evidence]:
        scores: dict[str, float] = {}
        evidence: dict[str, Evidence] = {}
        for items in lists:
            for rank, item in enumerate(items, start=1):
                scores[item.chunk_id] = scores.get(item.chunk_id, 0.0) + 1 / (rrf_k + rank)
                evidence[item.chunk_id] = item
        return [
            replace(evidence[key], score=scores[key])
            for key in sorted(scores, key=lambda x: (-scores[x], x))[:limit]
        ]

    async def search(self, query: Query, limit: int) -> list[Evidence]:
        results = await asyncio.gather(
            self.dense.search(query, max(limit * 3, 8)),
            self.keyword.search(query, max(limit * 3, 8)),
        )
        return self.fuse(list(results), limit)
