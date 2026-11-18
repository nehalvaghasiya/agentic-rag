"""Real worker and in-memory store through create-index-update-delete path."""

from agentic_rag.models.query import Query
from agentic_rag.models.upload import Upload


async def test_document_lifecycle(runtime, principal) -> None:
    jobs = await runtime.knowledge.submit(
        [Upload("update.txt", b"UniqueMercury marker is 4")], "demo", principal
    )
    assert jobs[0].status == "queued"
    await runtime.worker.once()
    assert jobs[0].status == "done"
    hits = await runtime.search.search(
        Query("UniqueMercury", ("demo",), principal), strategy="keyword"
    )
    target = next(h for h in hits if "UniqueMercury" in h.text)
    job = await runtime.knowledge.update(
        target.document_id, Upload("update.txt", b"UniqueSaturn marker is 7"), principal
    )
    await runtime.worker.once()
    assert job.status == "done"
    assert not await runtime.search.get([target.chunk_id], principal)
    await runtime.knowledge.delete(target.document_id, principal)
    assert not await runtime.search.search(
        Query("UniqueSaturn", ("demo",), principal), strategy="keyword"
    )
