"""Leased ingestion jobs and atomic publication of complete document revisions."""

import asyncio
from typing import Any

from agentic_rag.data.repository import Repository
from agentic_rag.knowledge.chunker import Chunker
from agentic_rag.knowledge.parser import ParserRegistry
from agentic_rag.models.principal import Principal
from agentic_rag.models.upload import Upload
from agentic_rag.ops.metrics import Metrics
from agentic_rag.ops.trace import TraceService
from agentic_rag.providers.identity import embedding_identity


class IngestWorker:
    def __init__(
        self,
        store: Repository,
        embed: Any,
        parser: ParserRegistry | None = None,
        chunker: Chunker | None = None,
        metrics: Metrics | None = None,
        trace: TraceService | None = None,
        tenant_id: str = "demo-tenant",
    ) -> None:
        self.store, self.embed = store, embed
        self.parser, self.chunker = parser or ParserRegistry(), chunker or Chunker()
        self.metrics, self.trace = metrics, trace or TraceService()
        self.principal = Principal("ingest-worker", tenant_id, frozenset({"admin"}))
        self.running = False

    async def once(self, principal: Principal | None = None) -> bool:
        p = principal or self.principal
        claimed = await self.store.claim_job(p)
        if not claimed:
            return False
        job, doc, blob = claimed
        try:
            sections = self.parser.parse(Upload(doc.title, blob, doc.content_type))
            chunks = self.chunker.split(doc, sections)
            with self.trace.span("rag.ingest.embed"):
                vectors = await self.embed.documents([c.text for c in chunks])
            await self.store.publish(
                job,
                doc,
                chunks,
                vectors,
                embedding_identity(self.embed),
                p,
            )
            await self.store.audit(
                {"action": "index", "document": doc.id, "chunks": len(chunks)}, p
            )
            if self.metrics:
                self.metrics.ingest.labels("ok").inc()
        except Exception as exc:
            await self.store.fail_job(job, type(exc).__name__, p)
            if self.metrics:
                self.metrics.ingest.labels("error").inc()
        return True

    async def run(self, poll_seconds: float = 0.25) -> None:
        self.running = True
        while self.running:
            if not await self.once():
                await asyncio.sleep(poll_seconds)

    def stop(self) -> None:
        self.running = False
