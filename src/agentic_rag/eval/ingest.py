"""Knowledge ingestion accounting from actual document/job state."""

from agentic_rag.data.fake import FakeStore


class IngestMetrics:
    def score(self, store: FakeStore) -> dict[str, float | None]:
        jobs = list(store.jobs.values())
        docs = list(store.docs.values())
        ready = sum(d.status == "ready" for d in docs)
        return {
            "parse_success_rate": sum(j.status == "done" for j in jobs) / len(jobs)
            if jobs
            else None,
            "index_ready_rate": ready / len(docs) if docs else None,
            "document_count": float(len(docs)),
            "chunk_count": float(len(store.chunks)),
        }
