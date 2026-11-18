"""Two tenants must never share documents, citations, sessions or memories."""

import pytest

from agentic_rag.models.principal import Principal
from agentic_rag.models.query import Query
from agentic_rag.models.upload import Upload


async def test_cross_tenant_access(runtime, principal) -> None:
    victim = await runtime.knowledge.submit(
        [Upload("private.txt", b"SuperPrivateNonce ZX-987")], "demo", principal
    )
    await runtime.worker.once()
    other = Principal("outsider", "other-tenant")
    with pytest.raises(PermissionError):
        await runtime.agent.run(Query("SuperPrivateNonce", ("demo",), other), mode="agentic")
    hits = await runtime.search.search(Query("SuperPrivateNonce", (), other), strategy="hybrid")
    assert hits == []
    target = next(c for c in runtime.store.chunks.values() if "SuperPrivateNonce" in c.text)
    assert not await runtime.search.get([target.id], other)
    with pytest.raises(PermissionError):
        await runtime.knowledge.status(victim[0].id, other)


async def test_acl_revocation(runtime, principal) -> None:
    jobs = await runtime.knowledge.submit(
        [Upload("restrict.txt", b"HiddenScopeExample")], "demo", principal
    )
    await runtime.worker.once()
    doc = runtime.store.docs[jobs[0].document_id]
    doc.groups = frozenset({"special"})
    doc.owner = "somebody-else"
    doc.acl_version += 1
    reader = Principal("reader", "demo-tenant")
    assert all(
        "HiddenScopeExample" not in e.text
        for e in await runtime.search.search(Query("HiddenScopeExample", ("demo",), reader))
    )
    assert await runtime.search.search(Query("HiddenScopeExample", ("demo",), principal))
