"""Trace and metric instrumentation for observable ingestion and tool outcomes."""

from agentic_rag.models.budget import Budget
from agentic_rag.models.run import Run
from agentic_rag.tools.base import ToolContext


async def test_metrics_include_completed_ingestion_and_tool(runtime, principal) -> None:
    await runtime.repo.begin_run(
        Run("measured", principal.tenant_id, principal.user_id), None, "test", principal
    )
    ctx = ToolContext(principal, "measured", ("demo",))
    await runtime.agent.runner.execute(
        "calculate", {"a": 2, "b": 3, "operation": "add"}, ctx, Budget()
    )
    exported = runtime.metrics.export().decode("utf-8")
    assert 'rag_ingest_total{outcome="ok"}' in exported
    assert 'rag_tools_total{name="calculate",status="ok"}' in exported
    assert "rag_request_seconds" in exported


def test_trace_spans_are_safe(runtime) -> None:
    with runtime.trace.span("rag.test", {"operation": "read"}):
        pass
