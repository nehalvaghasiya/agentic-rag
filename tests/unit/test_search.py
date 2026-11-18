"""No tenant leaks; deterministic dense/keyword/RRF/rerank contracts."""

import pytest

from agentic_rag.models.principal import Principal
from agentic_rag.models.query import Query
from agentic_rag.search.hybrid import HybridSearch


async def test_search_modes(runtime, principal) -> None:
    query = Query("2026 refund window", ("demo",), principal)
    for strategy in ("dense", "keyword", "hybrid", "advanced"):
        results = await runtime.search.search(query, strategy=strategy)
        assert results and any("2026" in r.text for r in results)
        assert len(results) <= 5
        assert all(r.tenant_id == "demo-tenant" for r in results)
    with pytest.raises(ValueError):
        await runtime.search.search(query, strategy="magic")
    other = Principal("user", "other-tenant")
    with pytest.raises(PermissionError):
        await runtime.search.search(Query(query.text, query.kb_ids, other))


def test_rrf_fusion(runtime, principal) -> None:
    example = runtime.store.allowed_chunks(principal, ("demo",))[:2]
    assert len(example) == 2
    a, b = [runtime.store.evidence(c, 0.9) for c in example]
    ranked = HybridSearch(runtime.search.dense, runtime.search.keyword).fuse([[a, b], [b, a]], 2)
    assert len(ranked) == 2 and ranked[0].score == pytest.approx(ranked[1].score)
