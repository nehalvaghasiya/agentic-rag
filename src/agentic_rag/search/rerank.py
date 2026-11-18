"""Cheap deterministic demo reranker (production may use a cross encoder)."""

from dataclasses import replace

from agentic_rag.models.evidence import Evidence
from agentic_rag.search.keyword import tokens


class Reranker:
    def rank(self, text: str, candidates: list[Evidence], limit: int) -> list[Evidence]:
        query = set(tokens(text))
        scored = []
        for item in candidates:
            overlap = len(query.intersection(tokens(item.text))) / max(1, len(query))
            scored.append(replace(item, score=item.score + 0.05 * overlap))
        return sorted(scored, key=lambda x: (-x.score, x.chunk_id))[:limit]
