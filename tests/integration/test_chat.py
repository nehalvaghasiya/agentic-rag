"""Behavioral regressions for the unified conversation and adaptive routes."""

import pytest

from agentic_rag.data.repository import ConflictError
from agentic_rag.models.principal import Principal
from agentic_rag.models.query import Query
from agentic_rag.models.run import Run


@pytest.mark.parametrize("text", ["Hello", "Why is the sky blue?", "Explain Python decorators"])
async def test_general_chat_skips_retrieval_and_agents(runtime, principal, monkeypatch, text):
    async def unexpected(*args, **kwargs):
        raise AssertionError("General conversation must not retrieve documents")

    monkeypatch.setattr(runtime.search, "search", unexpected)
    answer = await runtime.agent.run(Query(text, ("demo",), principal))
    assert answer.mode == "direct"
    assert answer.text and "cannot answer" not in answer.text
    events = runtime.store.events[answer.run_id]
    assert not any(e.type in {"plan", "agent_started", "tool_started", "retrieval"} for e in events)
    assert any(e.type == "route" for e in events)


async def test_fast_rag_skips_planner_and_keeps_citations(runtime, principal, monkeypatch):
    monkeypatch.setattr(
        runtime.planner if hasattr(runtime, "planner") else runtime.agent.planner,
        "plan",
        lambda *args: pytest.fail("Fast RAG invoked a planner"),
    )
    answer = await runtime.agent.run(
        Query("What is the refund window in policy 2026?", ("demo",), principal)
    )
    assert answer.mode == "baseline" and answer.supported and answer.citations
    assert "[1]" in answer.text
    assert not any(e.type == "agent_started" for e in runtime.store.events[answer.run_id])


async def test_history_is_shared_between_routes_and_users_are_isolated(runtime, principal):
    session = await runtime.sessions.create(principal, kb_ids=["demo"])
    sid = session["id"]
    await runtime.agent.run(Query("My name is Nehal.", ("demo",), principal, sid))
    await runtime.agent.run(
        Query("What is the refund window in policy 2026?", ("demo",), principal, sid)
    )
    answer = await runtime.agent.run(Query("What is my name?", ("demo",), principal, sid))
    assert "Nehal" in answer.text and answer.mode == "direct"
    with pytest.raises(PermissionError):
        await runtime.sessions.read(sid, Principal("different-user", principal.tenant_id))
    await runtime.sessions.clear(sid, principal)
    with pytest.raises(PermissionError):
        await runtime.repo.get_run(answer.run_id, principal)


async def test_empty_kb_scope_does_not_search_all_documents(runtime, principal):
    assert await runtime.search.search(Query("refund window", (), principal)) == []
    answer = await runtime.agent.run(
        Query("What is the refund window in the policy?", (), principal)
    )
    assert "attach" in answer.text.lower() and not answer.citations


async def test_cache_hit_has_origin_but_no_fabricated_execution(runtime, principal):
    first = await runtime.agent.run(
        Query("What is the refund window in policy 2026?", ("demo",), principal)
    )
    second = await runtime.agent.run(
        Query("What is the refund window in policy 2026?", ("demo",), principal)
    )
    run = await runtime.repo.get_run(second.run_id, principal)
    assert run.served_from_cache and run.origin_run_id == first.run_id
    assert second.text == first.text
    assert not any(
        e.type in {"generation", "retrieval", "tool_started"}
        for e in runtime.store.events[second.run_id]
    )
    source = (await runtime.search.get(list(first.citations), principal))[0]
    await runtime.knowledge.delete(source.document_id, principal)
    third = await runtime.agent.run(
        Query("What is the refund window in policy 2026?", ("demo",), principal)
    )
    assert not (await runtime.repo.get_run(third.run_id, principal)).served_from_cache
    assert source.chunk_id not in third.citations


async def test_complex_route_emits_real_specialist_calls(runtime, principal):
    answer = await runtime.agent.run(
        Query("Compare 2025 and 2026 refund windows", ("demo",), principal)
    )
    assert answer.mode == "agentic" and answer.supported and len(answer.citations) >= 2
    events = runtime.store.events[answer.run_id]
    assert any(e.type == "agent_started" and e.data["name"] == "ResearchAgent" for e in events)
    assert sum(e.type == "tool_started" for e in events) >= 2
    assert sum(e.type == "agent_started" for e in events) == sum(
        e.type == "agent_finished" for e in events
    )


async def test_idempotency_and_active_turn_conflicts(runtime, principal):
    session = await runtime.sessions.create(principal)
    run = Run(
        "r1",
        principal.tenant_id,
        principal.user_id,
        session_id=session["id"],
        client_message_id="m1",
    )
    _, created = await runtime.repo.begin_run(run, None, "same", principal)
    assert created
    again, created = await runtime.repo.begin_run(
        Run(
            "r2",
            principal.tenant_id,
            principal.user_id,
            session_id=session["id"],
            client_message_id="m1",
        ),
        None,
        "same",
        principal,
    )
    assert not created and again.id == "r1"
    with pytest.raises(ConflictError):
        await runtime.repo.begin_run(
            Run(
                "r3",
                principal.tenant_id,
                principal.user_id,
                session_id=session["id"],
                client_message_id="m1",
            ),
            None,
            "different",
            principal,
        )
    with pytest.raises(ConflictError):
        await runtime.repo.begin_run(
            Run(
                "r4",
                principal.tenant_id,
                principal.user_id,
                session_id=session["id"],
                client_message_id="m2",
            ),
            None,
            "new",
            principal,
        )


async def test_cancellation_has_exactly_one_terminal_event(runtime, principal):
    session = await runtime.sessions.create(principal)
    run = Run("cancel-test", principal.tenant_id, principal.user_id, session_id=session["id"])
    await runtime.repo.begin_run(run, None, "cancel", principal)
    await runtime.agent.cancel(run.id, principal)
    await runtime.agent.cancel(run.id, principal)
    events = await runtime.repo.events(run.id, principal)
    assert [e.type for e in events] == ["cancelled"]


async def test_failed_and_cancelled_turns_do_not_enter_context(runtime, principal):
    session = await runtime.sessions.create(principal)
    run = Run("incomplete", principal.tenant_id, principal.user_id, session_id=session["id"])
    message = {
        "id": "u-incomplete",
        "role": "user",
        "content": "Wrong context sentinel",
        "status": "completed",
        "run_id": run.id,
        "created_at": "2026-11-17T00:00:00Z",
    }
    await runtime.repo.begin_run(run, message, "x", principal)
    await runtime.agent.cancel(run.id, principal)
    history, _ = await runtime.sessions.context(session["id"], principal, "next")
    assert not history


async def test_simple_followup_stays_fast_and_general_deep_does_not_search(
    runtime, principal, monkeypatch
):
    session = await runtime.sessions.create(principal, kb_ids=["demo"])
    await runtime.agent.run(
        Query("What is the refund window in policy 2026?", ("demo",), principal, session["id"])
    )
    followup = await runtime.agent.run(
        Query("What about its 2025 version?", ("demo",), principal, session["id"])
    )
    assert followup.mode == "baseline" and "14 days" in followup.text

    async def unexpected(*args, **kwargs):
        raise AssertionError("General complex reasoning must not search attached documents")

    monkeypatch.setattr(runtime.search, "search", unexpected)
    answer = await runtime.agent.run(
        Query("Design a Python migration plan with multiple constraints", ("demo",), principal)
    )
    assert answer.mode == "agentic" and not answer.citations
    events = await runtime.repo.events(answer.run_id, principal)
    assert any(e.type == "agent_started" and e.data["name"] == "ReasoningAgent" for e in events)
    assert not any(e.type == "tool_started" for e in events)


async def test_fast_rag_visibly_escalates_for_causal_changes(runtime, principal):
    answer = await runtime.agent.run(
        Query("Why did the refund window change?", ("demo",), principal)
    )
    assert answer.mode == "agentic"
    assert any(e.type == "escalation" for e in await runtime.repo.events(answer.run_id, principal))


@pytest.mark.parametrize(
    "question",
    [
        "Compare policy 2025 and policy 2026 and calculate the difference in days",
        "Compare the 2025 and 2026 refund windows and calculate the difference in days",
    ],
)
async def test_document_and_calculator_results_keep_both_kinds_of_provenance(
    runtime, principal, question
):
    answer = await runtime.agent.run(
        Query(
            question,
            ("demo",),
            principal,
        )
    )
    run = await runtime.repo.get_run(answer.run_id, principal)
    assert answer.supported
    assert {s["kind"] for s in run.sources} == {"document", "tool"}
    assert any(s.get("tool") == "calculate" for s in run.sources)
    assert "16.0" in answer.text


async def test_background_summary_is_bounded_and_keeps_older_user_facts(runtime, principal):
    session = await runtime.sessions.create(principal)
    for text in ["My name is Nehal."] + [f"Write a short greeting {i}" for i in range(9)]:
        await runtime.agent.run(Query(text, (), principal, session["id"]))
    await runtime.sessions.summarize(session["id"], principal)
    restored = await runtime.sessions.read(session["id"], principal)
    assert restored["summary_status"] == "completed" and len(restored["summary"]) <= 4000
    history, info = await runtime.sessions.context(session["id"], principal, "next")
    assert info["summary_used"] and len(history) <= 17
    answer = await runtime.agent.run(Query("What is my name?", (), principal, session["id"]))
    assert "Nehal" in answer.text
    changed_roles = Principal(principal.user_id, principal.tenant_id, frozenset({"admin"}))
    assert not (await runtime.sessions.read(session["id"], changed_roles))["summary"]


async def test_admin_role_does_not_grant_other_users_private_run_history(runtime, principal):
    answer = await runtime.agent.run(Query("Hello", (), principal))
    with pytest.raises(PermissionError):
        await runtime.repo.get_run(
            answer.run_id, Principal("another-admin", principal.tenant_id, frozenset({"admin"}))
        )
    await runtime.repo.log(answer.run_id, "generation", {"title": "Late activity"}, principal)
    assert (await runtime.repo.events(answer.run_id, principal))[-1].type == "complete"


async def test_uncertain_routing_asks_for_clarification_and_understands_the_reply(
    runtime, principal, monkeypatch
):
    async def uncertain(*args, **kwargs):
        return {"mode": "clarify", "reason": "Source requirement is ambiguous"}

    monkeypatch.setattr(runtime.chat, "classify", uncertain)
    session = await runtime.sessions.create(principal, kb_ids=["demo"])
    first = await runtime.agent.run(
        Query("How does Saffron work?", ("demo",), principal, session["id"])
    )
    assert first.text == "Should I answer generally or use the attached knowledge base?"
    general = await runtime.agent.run(
        Query("Answer generally", ("demo",), principal, session["id"])
    )
    assert general.mode == "direct" and "Saffron" in general.text


async def test_malformed_route_classification_asks_for_clarification(
    runtime, principal, monkeypatch
):
    async def malformed(*args, **kwargs):
        raise ValueError("Invalid route classification")

    monkeypatch.setattr(runtime.chat, "classify", malformed)
    answer = await runtime.agent.run(Query("How does Saffron work?", ("demo",), principal))
    assert answer.mode == "direct"
    assert answer.text == "Should I answer generally or use the attached knowledge base?"
    assert not answer.citations


async def test_malformed_assessment_is_retried_with_visible_activity(
    runtime, principal, monkeypatch
):
    original = runtime.chat.assess
    calls = 0

    async def flaky(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("Invalid support assessment")
        return await original(*args, **kwargs)

    monkeypatch.setattr(runtime.chat, "assess", flaky)
    answer = await runtime.agent.run(
        Query("Compare the 2025 and 2026 refund windows", ("demo",), principal)
    )
    assert answer.supported and calls == 2
    assert any(
        e.type == "retry" and e.data["title"] == "Retrying support assessment"
        for e in await runtime.repo.events(answer.run_id, principal)
    )


async def test_agentic_generation_repairs_missing_citations(runtime, principal, monkeypatch):
    original = runtime.chat.complete
    grounded_calls = 0

    async def missing_citations(*args, **kwargs):
        nonlocal grounded_calls
        if kwargs.get("grounded"):
            grounded_calls += 1
            if grounded_calls == 1:
                return "The refund windows are 14 days and 30 days."
        return await original(*args, **kwargs)

    monkeypatch.setattr(runtime.chat, "complete", missing_citations)
    answer = await runtime.agent.run(
        Query("Compare the 2025 and 2026 refund windows", ("demo",), principal)
    )
    assert answer.supported and answer.citations and grounded_calls == 2
    assert any(
        e.type == "retry" and e.data["title"] == "Repairing document citations"
        for e in await runtime.repo.events(answer.run_id, principal)
    )
