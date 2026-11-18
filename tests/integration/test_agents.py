"""Three real modes, actual tool events, bounded multi-step retrieval."""

from agentic_rag.models.query import Query


async def test_agentic_vs_nonagentic(runtime, principal) -> None:
    query = Query("Compare 2025 and 2026 refund windows", ("demo",), principal)
    for mode in ("baseline", "advanced", "agentic"):
        answer = await runtime.agent.run(query, mode=mode)
        run = runtime.store.runs[answer.run_id]
        assert run.status == "completed"
        assert answer.supported and answer.citations
        if mode == "agentic":
            assert "14 days" in answer.text and "30 days" in answer.text
        events = runtime.store.events[answer.run_id]
        if mode == "agentic":
            assert any(e.type == "tool_started" and e.data["name"] == "search" for e in events)
            assert run.tool_calls >= 2
        else:
            assert run.tool_calls == 0
        assert events[-1].type == "complete"


async def test_sql_structured_agent(runtime, principal) -> None:
    answer = await runtime.agent.run(
        Query("What is the invoice total?", ("demo",), principal), mode="agentic"
    )
    assert "200.0" in answer.text
    assert answer.supported
    events = runtime.store.events[answer.run_id]
    assert any(e.type == "tool_started" and e.data["name"] == "sql" for e in events)
