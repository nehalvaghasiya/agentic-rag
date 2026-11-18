"""Fault simulation: retries, invalid transport inputs, cancellation and replay safety."""

import pytest

from agentic_rag.models.budget import Budget
from agentic_rag.models.query import Query
from agentic_rag.models.run import Run
from agentic_rag.models.upload import Upload
from agentic_rag.tools.base import ToolContext


async def test_unsafe_replay_is_not_a_new_tool_call(runtime, principal) -> None:
    await runtime.repo.begin_run(
        Run("replay-run", principal.tenant_id, principal.user_id), None, "test", principal
    )
    ctx = ToolContext(principal, "replay-run", ("demo",))
    original = await runtime.agent.runner.execute(
        "calculate",
        {"a": 2, "b": 3, "operation": "multiply"},
        ctx,
        Budget(max_tool_calls=1),
        call_id="stable",
    )
    assert original.output["result"] == 6
    with pytest.raises(PermissionError, match="replay mismatch"):
        await runtime.agent.runner.execute(
            "calculate",
            {"a": 20, "b": 3, "operation": "multiply"},
            ctx,
            Budget(max_tool_calls=1),
            call_id="stable",
        )
    assert runtime.agent.runner.counts[ctx.run_id] == 1


async def test_corrupt_source_never_enters_index(runtime, principal) -> None:
    with pytest.raises(ValueError):
        await runtime.knowledge.submit([Upload("wrong.pdf", b"NOT_A_PDF")], "demo", principal)
    assert not any(doc.title == "wrong.pdf" for doc in runtime.store.docs.values())


async def test_failed_embedding_keeps_document_unsearchable(runtime, principal) -> None:
    jobs = await runtime.knowledge.submit(
        [Upload("temporary.txt", b"recovery control fact")], "demo", principal
    )
    doc = runtime.store.docs[jobs[0].document_id]

    class Down:
        async def documents(self, texts):
            raise TimeoutError("offline provider")

    original = runtime.worker.embed
    runtime.worker.embed = Down()
    try:
        assert await runtime.worker.once()
    finally:
        runtime.worker.embed = original
    assert doc.status == "failed"
    assert jobs[0].status == "failed"
    assert not any(chunk.document_id == doc.id for chunk in runtime.store.chunks.values())


async def test_completed_run_is_not_replayed(runtime, principal) -> None:
    result = await runtime.agent.run(
        Query("What is refund policy?", ("demo",), principal), mode="agentic"
    )
    with pytest.raises(ValueError, match="Duplicate"):
        await runtime.agent.run(
            Query("What is refund policy?", ("demo",), principal),
            mode="agentic",
            run_id=result.run_id,
        )


async def test_cancelled_before_execution_bails(runtime, principal) -> None:
    result = await runtime.agent.run(
        Query("What is refund policy?", ("demo",), principal), mode="baseline"
    )
    await runtime.agent.cancel(result.run_id, principal)
    assert runtime.store.runs[result.run_id].status == "completed"
