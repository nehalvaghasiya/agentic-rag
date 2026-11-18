"""Document-level behavior: screenshot regressions, coverage, attribution and history."""

import pytest

from agentic_rag.models.grounded import GroundingError
from agentic_rag.models.query import Query
from agentic_rag.models.upload import Upload


@pytest.fixture
async def plan(runtime, principal):
    kb = await runtime.knowledge.create_kb("Harbor library plan", principal)
    text = "# Harbor digitization plan\n\n" + "\n\n".join(
        f"## Phase {i}\nMilestone {i}: catalog {i * 1000} books. "
        + f"Phase {i} preserves the original metadata and supports offline access. " * 25
        for i in range(1, 9)
    )
    await runtime.knowledge.submit([Upload("harbor-plan.md", text.encode())], kb["id"], principal)
    await runtime.worker.once(principal)
    return kb["id"]


@pytest.mark.parametrize(
    "question",
    [
        "whats this about",
        "whats this plan about",
        "Give me top 5 takeaways from this plan",
        "Summarize it",
        "Create an implementation checklist from this document",
    ],
)
async def test_document_requests_read_all_passages_without_classifier_or_agents(
    runtime, principal, plan, monkeypatch, question
):
    async def unexpected(*args, **kwargs):
        pytest.fail(
            "A clear document request used intent classification or narrow semantic retrieval"
        )

    monkeypatch.setattr(runtime.chat, "classify", unexpected)
    monkeypatch.setattr(runtime.search, "search", unexpected)
    answer = await runtime.agent.run(Query(question, (plan,), principal))
    run = await runtime.repo.get_run(answer.run_id, principal)
    assert answer.mode == "baseline" and answer.supported and answer.citations
    assert run.coverage["read_chunks"] == run.coverage["total_chunks"]
    assert run.coverage["read_chunks"] > 4
    assert not any(e.type == "agent_started" for e in await runtime.repo.events(run.id, principal))


async def test_clarification_reply_recovers_the_original_request(
    runtime, principal, plan, monkeypatch
):
    session = await runtime.sessions.create(principal, kb_ids=[plan])

    async def uncertain(*args, **kwargs):
        return {"mode": "clarify", "reason": "Ambiguous product name"}

    monkeypatch.setattr(runtime.chat, "classify", uncertain)
    await runtime.agent.run(Query("How does Saffron work?", (plan,), principal, session["id"]))
    resolved = []
    original = runtime.chat.answer_document

    async def capture(messages, evidence, **kwargs):
        resolved.append(messages[-1]["content"])
        return await original(messages, evidence, **kwargs)

    monkeypatch.setattr(runtime.chat, "answer_document", capture)
    answer = await runtime.agent.run(
        Query("use attached knowledge", (plan,), principal, session["id"])
    )
    assert answer.supported
    assert "Saffron" in resolved[-1] and "According to attached documents:" in resolved[-1]


async def test_long_document_section_summaries_are_cached_and_cover_later_sections(
    runtime, principal, plan, monkeypatch
):
    monkeypatch.setattr(runtime.agent.documents, "SOURCE_BUDGET", 6500)
    seen = []
    original = runtime.chat.answer_document

    async def capture(messages, evidence, **kwargs):
        if "These are section notes" in kwargs.get("instruction", ""):
            seen.extend(e.text for e in evidence)
        return await original(messages, evidence, **kwargs)

    monkeypatch.setattr(runtime.chat, "answer_document", capture)
    first = await runtime.agent.run(Query("whats this plan about", (plan,), principal))
    run = await runtime.repo.get_run(first.run_id, principal)
    assert first.supported and run.coverage["strategy"] == "map_reduce"
    assert run.coverage["read_chunks"] == run.coverage["total_chunks"]
    assert any("Milestone 8:" in text for text in seen)
    calls = len(seen)
    second = await runtime.agent.run(
        Query("Give me the key takeaways from this plan", (plan,), principal)
    )
    assert second.supported and len(seen) == calls
    assert any(
        e.type == "cache"
        and e.data.get("layer") == "document_summary"
        and e.data["status"] == "hit"
        for e in await runtime.repo.events(second.run_id, principal)
    )


async def test_complex_document_plan_uses_the_graph_and_complete_read(runtime, principal, plan):
    answer = await runtime.agent.run(
        Query("Create a detailed implementation plan based on this document", (plan,), principal)
    )
    run = await runtime.repo.get_run(answer.run_id, principal)
    assert answer.mode == "agentic" and answer.supported
    assert run.coverage["total_chunks"] == run.coverage["read_chunks"] > 4
    assert any(
        e.type == "agent_started" and e.data["name"] == "ResearchAgent"
        for e in await runtime.repo.events(answer.run_id, principal)
    )


async def test_document_refusal_has_a_reason_and_is_excluded_from_context(
    runtime, principal, plan, monkeypatch
):
    async def invalid(*args, **kwargs):
        raise GroundingError("Unknown source label")

    monkeypatch.setattr(runtime.chat, "answer_document", invalid)
    session = await runtime.sessions.create(principal, kb_ids=[plan])
    answer = await runtime.agent.run(
        Query("whats this plan about", (plan,), principal, session["id"])
    )
    run = await runtime.repo.get_run(answer.run_id, principal)
    assert run.answer_status == "citation_error" and run.evidence_count > 4
    assert not answer.supported and not answer.citations and "source references" in answer.text
    history, _ = await runtime.sessions.context(session["id"], principal, "next")
    assert not history
    session["summary_status"] = "queued"
    await runtime.repo.save_session(session, principal)
    await runtime.sessions.summarize(session["id"], principal)
    assert (await runtime.sessions.read(session["id"], principal))["summary_status"] == "idle"


async def test_ambiguous_document_is_clarified_and_filename_reply_keeps_task(
    runtime, principal, plan
):
    await runtime.knowledge.submit(
        [Upload("other-plan.md", b"Other plan: run a local workshop.")], plan, principal
    )
    await runtime.worker.once(principal)
    session = await runtime.sessions.create(principal, kb_ids=[plan])
    first = await runtime.agent.run(
        Query("whats this plan about", (plan,), principal, session["id"])
    )
    assert first.text.startswith("Which document should I use?")
    second = await runtime.agent.run(Query("harbor-plan.md", (plan,), principal, session["id"]))
    assert second.supported
    run = await runtime.repo.get_run(second.run_id, principal)
    assert run.coverage["documents"] == ["harbor-plan.md"]


async def test_document_budget_limit_is_reported_without_claiming_full_coverage(
    runtime, principal, plan, monkeypatch
):
    monkeypatch.setattr(runtime.agent.documents, "MAX_BATCHES", 1)
    monkeypatch.setattr(runtime.agent.documents, "SOURCE_BUDGET", 1800)
    answer = await runtime.agent.run(Query("Summarize this plan", (plan,), principal))
    run = await runtime.repo.get_run(answer.run_id, principal)
    assert run.answer_status == "coverage_limit" and not answer.supported
    assert "not analyzed the whole file" in answer.text
    assert not run.coverage.get("read_chunks")


async def test_unrelated_question_after_document_answer_still_skips_retrieval(
    runtime, principal, plan, monkeypatch
):
    session = await runtime.sessions.create(principal, kb_ids=[plan])
    await runtime.agent.run(Query("whats this plan about", (plan,), principal, session["id"]))

    async def unexpected(*args, **kwargs):
        pytest.fail("General question used document retrieval")

    monkeypatch.setattr(runtime.search, "search", unexpected)
    monkeypatch.setattr(runtime.agent.documents, "prepare", unexpected)
    answer = await runtime.agent.run(
        Query("Explain Python decorators", (plan,), principal, session["id"])
    )
    assert answer.mode == "direct" and not answer.citations


async def test_document_reduction_can_retain_more_than_28000_characters_of_support(
    runtime, principal, monkeypatch
):
    from agentic_rag.models.grounded import GroundedAnswer, source_context_chars

    kb = await runtime.knowledge.create_kb("Dense source references", principal)
    text = "# Diverse plan\n\n" + "\n\n".join(
        f"## Requirement {i}\nRequirement {i} preserves validation evidence. " + "validation " * 100
        for i in range(24)
    )
    await runtime.knowledge.submit([Upload("dense-plan.md", text.encode())], kb["id"], principal)
    await runtime.worker.once(principal)
    calls = []

    async def source_attributed(messages, evidence, **kwargs):
        calls.append(source_context_chars(evidence))
        return GroundedAnswer(
            "Requirements are preserved. " + " ".join(f"[source:{e.chunk_id}]" for e in evidence),
            True,
        )

    monkeypatch.setattr(runtime.chat, "answer_document", source_attributed)
    answer = await runtime.agent.run(Query("whats this plan about", (kb["id"],), principal))
    run = await runtime.repo.get_run(answer.run_id, principal)
    assert answer.supported and run.answer_status == "answered"
    assert run.coverage["read_chunks"] == run.coverage["total_chunks"]
    assert run.coverage["strategy"] == "map_reduce" and calls[-1] > 28000


async def test_document_input_budget_preserves_sources_and_current_question(
    runtime, principal, monkeypatch
):
    from agentic_rag.models.budget import Budget
    from agentic_rag.models.grounded import DOCUMENT_PROMPT_RESERVE, source_context_chars

    original = runtime.chat.answer_document
    captured = []

    async def capture(messages, evidence, **kwargs):
        captured.append(messages)
        assert (
            source_context_chars(evidence)
            + DOCUMENT_PROMPT_RESERVE
            + len(kwargs.get("instruction", ""))
            + sum(len(m["content"]) for m in messages)
            <= 8000
        )
        return await original(messages, evidence, **kwargs)

    monkeypatch.setattr(runtime.chat, "answer_document", capture)
    history = tuple(
        {"role": role, "content": "Past discussion " + "x" * 1450}
        for role in ["user", "assistant", "user", "assistant"]
    )
    question = "What is the refund window in policy 2026?"
    answer = await runtime.agent.run(
        Query(question, ("demo",), principal, history=history), budget=Budget(max_input_tokens=2000)
    )
    assert answer.supported and len(captured[-1]) < 5
    assert captured[-1][-1]["content"] == question
    assert captured[-1][0]["role"] == "user"
    assert any(
        e.type == "context"
        and e.data["title"] == "Conversation context adjusted for document reading"
        for e in await runtime.repo.events(answer.run_id, principal)
    )


async def test_tight_document_input_budget_reports_scope_limit(
    runtime, principal, plan, monkeypatch
):
    from agentic_rag.models.budget import Budget

    async def unexpected(*args, **kwargs):
        pytest.fail("An over-budget document was sent to the model")

    monkeypatch.setattr(runtime.chat, "answer_document", unexpected)
    answer = await runtime.agent.run(
        Query("Summarize this plan", (plan,), principal), budget=Budget(max_input_tokens=1000)
    )
    run = await runtime.repo.get_run(answer.run_id, principal)
    assert not answer.supported and run.answer_status == "coverage_limit"
    assert "configured input budget" in answer.text


async def test_incomplete_but_supported_deep_answer_is_repaired_with_feedback(
    runtime, principal, plan, monkeypatch
):
    original_assess = runtime.chat.assess
    original_answer = runtime.chat.answer_document
    calls = 0
    instructions = []

    async def assess(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return {
                "supported": True,
                "complete": False,
                "missing": "Include source-defined acceptance checks.",
                "conflict": False,
            }
        return await original_assess(*args, **kwargs)

    async def answer(*args, **kwargs):
        instructions.append(kwargs.get("instruction", ""))
        return await original_answer(*args, **kwargs)

    monkeypatch.setattr(runtime.chat, "assess", assess)
    monkeypatch.setattr(runtime.chat, "answer_document", answer)
    result = await runtime.agent.run(
        Query("Create a detailed implementation plan based on this document", (plan,), principal)
    )
    assert result.supported and calls == 2
    assert "Include source-defined acceptance checks." in instructions[-1]
    assert any(
        e.type == "verification" and e.data.get("reason_code") == "INCOMPLETE_TASK"
        for e in await runtime.repo.events(result.run_id, principal)
    )


async def test_plan_format_repair_is_reported_separately_from_citation_repair(
    runtime, principal, plan, monkeypatch
):
    original = runtime.chat.answer_document
    calls = 0

    async def wrong_format(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise GroundingError("The implementation plan needs actionable phases", kind="format")
        assert "actionable phases" in kwargs["instruction"]
        return await original(*args, **kwargs)

    monkeypatch.setattr(runtime.chat, "answer_document", wrong_format)
    answer = await runtime.agent.run(
        Query("Create an implementation checklist from this document", (plan,), principal)
    )
    assert answer.supported
    assert any(
        e.type == "retry" and e.data["title"] == "Repairing requested document format"
        for e in await runtime.repo.events(answer.run_id, principal)
    )


async def test_deep_provider_timeout_preserves_document_coverage(
    runtime, principal, plan, monkeypatch
):
    import httpx

    from agentic_rag.models.budget import Budget

    async def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("Test provider timeout")

    monkeypatch.setattr(runtime.chat, "assess", timeout)
    with pytest.raises(httpx.ReadTimeout):
        await runtime.agent.run(
            Query(
                "Create a detailed implementation plan based on this document", (plan,), principal
            ),
            budget=Budget(max_retries=0),
        )
    run = list(runtime.store.runs.values())[-1]
    assert run.status == "failed" and run.answer_status == "verification_failed"
    assert run.coverage["read_chunks"] == run.coverage["total_chunks"] > 4
    assert run.evidence_count > 4 and run.latency_ms > 0
    assert runtime.store.events[run.id][-1].data["code"] == "PROVIDER_TIMEOUT"


async def test_provider_rate_limit_has_a_specific_message_and_retry_reason(
    runtime, principal, plan, monkeypatch
):
    import httpx

    from agentic_rag.models.budget import Budget

    request = httpx.Request("POST", "https://models.invalid/v1/chat/completions")

    async def limited(*args, **kwargs):
        response = httpx.Response(429, request=request)
        raise httpx.HTTPStatusError("Rate limited", request=request, response=response)

    monkeypatch.setattr(runtime.chat, "answer_document", limited)
    with pytest.raises(httpx.HTTPStatusError):
        await runtime.agent.run(
            Query("whats this plan about", (plan,), principal), budget=Budget(max_retries=1)
        )
    run = list(runtime.store.runs.values())[-1]
    events = runtime.store.events[run.id]
    assert run.answer_status == "verification_failed" and "rate-limiting" in run.answer
    assert run.evidence_count > 4 and run.latency_ms > 0
    assert events[-1].data["code"] == "PROVIDER_RATE_LIMIT"
    assert any(
        e.type == "retry" and e.data.get("reason_code") == "PROVIDER_RATE_LIMIT" for e in events
    )


async def test_run_deadline_is_reported_separately_from_provider_failure(
    runtime, principal, plan, monkeypatch
):
    import asyncio

    from agentic_rag.models.budget import Budget

    async def slow(*args, **kwargs):
        await asyncio.sleep(1)

    monkeypatch.setattr(runtime.chat, "answer_document", slow)
    with pytest.raises(TimeoutError):
        await runtime.agent.run(
            Query("whats this plan about", (plan,), principal),
            budget=Budget(max_seconds=0.03, max_retries=0),
        )
    run = list(runtime.store.runs.values())[-1]
    assert run.status == "failed" and run.coverage["read_chunks"] > 4
    assert runtime.store.events[run.id][-1].data["code"] == "BUDGET_EXHAUSTED"
    assert "0.03-second limit" in run.answer


async def test_whole_document_graph_skips_unused_remote_planning(
    runtime, principal, plan, monkeypatch
):
    original = runtime.chat.complete

    async def complete(*args, **kwargs):
        if kwargs.get("instruction", "").startswith("Create an evidence collection plan"):
            raise AssertionError(
                "Whole-document reading does not use model-refined retrieval goals"
            )
        return await original(*args, **kwargs)

    monkeypatch.setattr(runtime.chat, "is_test_double", False)
    monkeypatch.setattr(runtime.chat, "complete", complete)
    answer = await runtime.agent.run(
        Query("Create a detailed implementation plan based on this document", (plan,), principal)
    )
    assert answer.supported and answer.mode == "agentic"
    assert any(
        e.type == "plan" and e.data.get("plan_method") == "whole_document_policy"
        for e in await runtime.repo.events(answer.run_id, principal)
    )


@pytest.mark.parametrize("custom_seconds", [None, 45.0])
async def test_only_default_complex_document_deadline_is_extended(
    runtime, principal, plan, custom_seconds
):
    from agentic_rag.models.budget import Budget

    answer = await runtime.agent.run(
        Query("Create a detailed implementation plan based on this document", (plan,), principal),
        budget=None if custom_seconds is None else Budget(max_seconds=custom_seconds),
    )
    assert answer.supported
    budgets = [
        e.data
        for e in await runtime.repo.events(answer.run_id, principal)
        if e.type == "budget" and e.data.get("max_seconds") == 180.0
    ]
    assert bool(budgets) == (custom_seconds is None)
