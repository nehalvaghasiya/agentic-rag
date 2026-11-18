"""Dense retrieval with cached query embeddings and explicit document scope."""

from typing import Any

from agentic_rag.data.cache import Cache, fingerprint
from agentic_rag.data.repository import Repository
from agentic_rag.models.evidence import Evidence
from agentic_rag.models.query import Query
from agentic_rag.providers.identity import embedding_identity


class DenseSearch:
    def __init__(self, store: Repository, embed: Any) -> None:
        self.store, self.embed, self.cache = store, embed, Cache(store)

    async def search(self, query: Query, limit: int) -> list[Evidence]:
        if not query.kb_ids:
            return []
        identity = embedding_identity(self.embed)
        key = "embedding:" + fingerprint([identity, query.text])
        cached = await self.cache.get(key, query.principal)
        if run_id := query.filters.get("run_id"):
            await self.store.log(
                run_id,
                "cache",
                {
                    "layer": "embedding",
                    "status": "hit" if cached else "miss",
                    "title": "Query embedding cache",
                    "description": f"Embedding model: {identity.split('@')[0]}",
                },
                query.principal,
            )
        if cached:
            vector = cached["vector"]
        else:
            vector = await self.embed.query(query.text)
            await self.cache.put(key, {"vector": vector}, query.principal, 86400)
        for kb_id in query.kb_ids:
            kb = await self.store.check_kb(kb_id, query.principal)
            if kb.get("embedding_model") and kb["embedding_model"] != identity:
                raise ValueError(
                    "Embedding model changed; create a new knowledge base and reingest"
                )
        return await self.store.dense(vector, query.kb_ids, query.principal, limit)
