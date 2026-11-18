"""Real pgvector/RLS tests. Supply a disposable migrated application database URL."""

import os
from uuid import uuid4

import pytest

from agentic_rag.core.config import Settings
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.models.principal import Principal
from agentic_rag.models.query import Query
from agentic_rag.models.upload import Upload


@pytest.fixture
async def postgres():
    url = os.environ.get("AGENTIC_RAG_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set AGENTIC_RAG_TEST_DATABASE_URL to a disposable migrated pgvector database")
    settings = Settings(
        environment="demo",
        store="postgres",
        provider="fake",
        embedding_provider="fake",
        database_url=url,
    )
    runtime = RuntimeFactory(settings)
    await runtime.open()
    yield runtime, settings
    await runtime.close()


async def test_postgres_documents_chat_events_and_checkpoints_survive_restart(postgres):
    runtime, settings = postgres
    p = Principal("owner", uuid4().hex, frozenset({"admin", "analyst"}))
    kb = await runtime.knowledge.create_kb("Refund policy", p)
    await runtime.knowledge.submit(
        [
            Upload("2025.md", b"Refund policy 2025: Refunds are allowed for 14 days."),
            Upload("2026.md", b"Refund policy 2026: Refunds are allowed for 30 days."),
        ],
        kb["id"],
        p,
    )
    while await runtime.worker.once(p):
        pass
    session = await runtime.sessions.create(p, kb_ids=[kb["id"]])
    answer = await runtime.agent.run(
        Query("Compare the 2025 and 2026 refund windows", (kb["id"],), p, session["id"])
    )
    assert answer.supported and len(answer.citations) == 2
    assert len(await runtime.repo.events(answer.run_id, p)) > 5
    await runtime.close()
    reopened = RuntimeFactory(settings)
    await reopened.open()
    try:
        restored = await reopened.sessions.read(session["id"], p)
        assert len(restored["messages"]) == 2
        assert restored["messages"][-1]["content"] == answer.text
        assert len(await reopened.search.get(list(answer.citations), p)) == 2
        config = {"configurable": {"thread_id": f"{p.tenant_id}:{p.user_id}:{answer.run_id}"}}
        snapshot = await reopened.agent.graph.aget_state(config)
        assert snapshot.values["sufficient"] is True
    finally:
        await reopened.close()


async def test_postgres_rls_and_cached_sources_are_rechecked(postgres):
    runtime, _ = postgres
    p = Principal("owner", uuid4().hex, frozenset({"admin"}))
    other = Principal("other", p.tenant_id)
    cross_tenant = Principal("other", uuid4().hex)
    kb = await runtime.knowledge.create_kb("Private reference", p)
    jobs = await runtime.knowledge.submit(
        [Upload("reference.md", b"Refund policy: the return window is 30 days.")], kb["id"], p
    )
    await runtime.worker.once(p)
    session = await runtime.sessions.create(p)
    with pytest.raises(PermissionError):
        await runtime.sessions.read(session["id"], other)
    with pytest.raises(PermissionError):
        await runtime.repo.check_kb(kb["id"], cross_tenant)
    async with runtime.store.transaction(other) as conn:
        rows = await (await conn.execute("SELECT id FROM rag.sessions")).fetchall()
        assert not rows  # PostgreSQL itself enforces user isolation.
    first = await runtime.agent.run(
        Query("What is the refund window in the policy?", (kb["id"],), other)
    )
    assert first.supported
    second = await runtime.agent.run(
        Query("What is the refund window in the policy?", (kb["id"],), other)
    )
    assert (await runtime.repo.get_run(second.run_id, other)).served_from_cache
    async with runtime.store.transaction(p) as conn:
        await conn.execute(
            "UPDATE rag.documents SET groups=ARRAY['finance'],acl_version=acl_version+1 WHERE id=%s",
            (jobs[0].document_id,),
        )
    assert not await runtime.search.get(list(first.citations), other)
    third = await runtime.agent.run(
        Query("What is the refund window in the policy?", (kb["id"],), other)
    )
    assert not third.supported
    assert not (await runtime.repo.get_run(third.run_id, other)).served_from_cache


async def test_postgres_supports_non1536_dimensions_and_exhausted_leases(postgres):
    runtime, _ = postgres
    from agentic_rag.providers.hash import HashEmbed

    embed = HashEmbed(3072)
    runtime.worker.embed = runtime.search.dense.embed = embed
    p = Principal("owner", uuid4().hex, frozenset({"admin"}))
    kb = await runtime.knowledge.create_kb("Dimensions", p)
    await runtime.knowledge.submit(
        [Upload("facts.md", b"Policy refund window is 30 days.")], kb["id"], p
    )
    await runtime.worker.once(p)
    answer = await runtime.agent.run(Query("What is the policy refund window?", (kb["id"],), p))
    assert answer.supported
    queued = (
        await runtime.knowledge.submit(
            [Upload("pending.md", b"Pending ingestion source.")], kb["id"], p
        )
    )[0]
    async with runtime.store.transaction(p) as conn:
        await conn.execute(
            "UPDATE rag.jobs SET status='running',attempts=3,lease_until=now()-interval '1 minute' WHERE id=%s",
            (queued.id,),
        )
    assert not await runtime.worker.once(p)
    job = await runtime.repo.get_job(queued.id, p)
    assert job.status == "failed" and job.error == "LeaseExhausted"


async def test_postgres_full_document_reads_are_ordered_and_recheck_acl(postgres):
    runtime, _ = postgres
    p = Principal("owner", uuid4().hex, frozenset({"admin"}))
    kb = await runtime.knowledge.create_kb("Ordered document", p)
    jobs = await runtime.knowledge.submit(
        [
            Upload(
                "plan.md",
                b"# First\nCatalog books.\n## Middle\nSupport offline access.\n## Last\nTest backup restoration.",
            )
        ],
        kb["id"],
        p,
    )
    await runtime.worker.once(p)
    chunks, total = await runtime.repo.document_chunks(jobs[0].document_id, p)
    assert total == len(chunks) == 3
    assert chunks[0].section == "First" and chunks[-1].section == "Last"
    other = Principal("reader", p.tenant_id)
    assert (await runtime.repo.document_chunks(jobs[0].document_id, other))[1] == 3
    async with runtime.store.transaction(p) as conn:
        await conn.execute(
            "UPDATE rag.documents SET groups=ARRAY['finance'] WHERE id=%s", (jobs[0].document_id,)
        )
    with pytest.raises(PermissionError):
        await runtime.repo.document_chunks(jobs[0].document_id, other)
    with pytest.raises(PermissionError):
        await runtime.repo.document_chunks(jobs[0].document_id, Principal("reader", uuid4().hex))


@pytest.mark.parametrize("delete_base", [False, True])
@pytest.mark.parametrize("running", [False, True])
async def test_postgres_originals_and_deletion_during_embedding(
    postgres, monkeypatch, delete_base, running
):
    import asyncio

    runtime, settings = postgres
    p = Principal("owner", uuid4().hex, frozenset({"admin"}))
    kb = await runtime.knowledge.create_kb("Managed originals", p)
    content = b"# Managed original\n\nSynthetic deletion race content."
    jobs = await runtime.knowledge.submit([Upload("original.md", content)], kb["id"], p)
    doc_id = jobs[0].document_id
    assert (await runtime.knowledge.original(doc_id, p))[1] == content
    restarted = RuntimeFactory(settings)
    await restarted.open()
    try:
        assert (await restarted.knowledge.original(doc_id, p))[1] == content
    finally:
        await restarted.close()
    outsider = Principal("outsider", uuid4().hex)
    with pytest.raises(PermissionError):
        await runtime.knowledge.original(doc_id, outsider)
    started, release = asyncio.Event(), asyncio.Event()
    original = runtime.worker.embed.documents

    async def delayed(texts):
        started.set()
        await release.wait()
        return await original(texts)

    monkeypatch.setattr(runtime.worker.embed, "documents", delayed)
    task = None
    if running:
        task = asyncio.create_task(runtime.worker.once(p))
        await asyncio.wait_for(started.wait(), 5)
    if delete_base:
        await asyncio.wait_for(runtime.knowledge.delete_kb(kb["id"], p), 5)
    else:
        await asyncio.wait_for(runtime.knowledge.delete(doc_id, p), 5)
    release.set()
    if task:
        await asyncio.wait_for(task, 5)
    assert (await runtime.knowledge.status(jobs[0].id, p)).error == "SourceDeleted"
    with pytest.raises(PermissionError):
        await runtime.knowledge.original(doc_id, p)
    async with runtime.repo.transaction(p) as conn:
        assert not await (
            await conn.execute("SELECT id FROM rag.chunks WHERE document_id=%s", (doc_id,))
        ).fetchall()
        assert not await (
            await conn.execute(
                "SELECT document_id FROM rag.contents WHERE document_id=%s", (doc_id,)
            )
        ).fetchall()


async def test_answer_versions_survive_restart_and_reauthorize_sources(postgres):
    from agentic_rag.api.runs import public_run
    from agentic_rag.memory.conversation import now
    from agentic_rag.models.run import Run

    runtime, settings = postgres
    p = Principal("version-owner", uuid4().hex, frozenset({"admin", "analyst"}))
    kb = await runtime.knowledge.create_kb("Version source", p)
    jobs = await runtime.knowledge.submit(
        [Upload("policy_2026.md", b"Refund policy 2026: The refund window is 30 days.")],
        kb["id"],
        p,
    )
    while await runtime.worker.once(p):
        pass
    session = await runtime.sessions.create(p, kb_ids=[kb["id"]])
    query = Query("What is the refund window in policy 2026?", (kb["id"],), p, session["id"])
    first = await runtime.agent.run(query)
    saved = await runtime.sessions.read(session["id"], p)
    mid = saved["messages"][-1]["id"]
    version = Run(
        uuid4().hex,
        p.tenant_id,
        p.user_id,
        session_id=session["id"],
        assistant_message_id=mid,
        regeneration_of_run_id=first.run_id,
        created_at=now(),
        kb_ids=[kb["id"]],
    )
    await runtime.repo.begin_run(version, None, "regeneration", p)
    second = await runtime.agent.run(query, run_id=version.id)
    assert not (await runtime.repo.get_run(second.run_id, p)).served_from_cache
    await runtime.repo.select_version(session["id"], mid, first.run_id, second.run_id, p)
    await runtime.close()
    reopened = RuntimeFactory(settings)
    await reopened.open()
    try:
        restored = await reopened.sessions.read(session["id"], p)
        assert len(restored["messages"]) == 2
        answer = restored["messages"][-1]
        assert answer["id"] == mid and answer["run_id"] == first.run_id
        assert len(answer["versions"]) == 2
        history, _ = await reopened.sessions.context(session["id"], p, "next")
        assert len(history) == 2 and history[-1]["content"] == first.text
        await reopened.repo.select_version(session["id"], mid, second.run_id, first.run_id, p)
        await reopened.knowledge.delete(jobs[0].document_id, p)
        for uid in [first.run_id, second.run_id]:
            safe = await public_run(await reopened.repo.get_run(uid, p), reopened, p)
            assert all(
                not source["available"] and not source["excerpt"] for source in safe["sources"]
            )
            assert safe["answer"] == "This answer used a source that is no longer available."
    finally:
        await reopened.close()
