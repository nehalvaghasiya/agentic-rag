"""Source attribution is validated independently of model prose and formatting."""

import json

import httpx
import pytest

from agentic_rag.models.evidence import Evidence
from agentic_rag.models.grounded import GroundingError, render_grounded
from agentic_rag.providers.openai import OpenAIChat


@pytest.fixture
def evidence():
    return [
        Evidence(
            "a" * 24,
            "doc",
            1,
            "The Harbor plan digitizes 12,000 books.",
            1.0,
            None,
            None,
            "Collection",
            "tenant",
            1,
            "harbor.md",
        )
    ]


def test_structured_attribution_renders_canonical_inline_citations(evidence):
    result = render_grounded(
        {
            "status": "answered",
            "blocks": [{"text": "Digitize 12,000 books 【S1】.", "sources": ["S1"]}],
        },
        evidence,
    )
    assert result.supported and "[source:" + "a" * 24 + "]" in result.text
    assert "【" not in result.text and "[S1]" not in result.text


@pytest.mark.parametrize(
    "block",
    [
        {"text": "A fabricated claim", "sources": ["S999"]},
        {"text": "An uncited claim", "sources": []},
        {"text": "Claim 【S999】", "sources": ["S1"]},
    ],
)
def test_invalid_or_missing_source_references_are_rejected(evidence, block):
    with pytest.raises(GroundingError):
        render_grounded({"status": "answered", "blocks": [block]}, evidence)


def test_insufficient_evidence_preserves_a_specific_reason(evidence):
    result = render_grounded(
        {
            "status": "insufficient_evidence",
            "blocks": [],
            "reason": "The document does not state a deadline.",
        },
        evidence,
    )
    assert not result.supported and "deadline" in result.reason


async def test_document_provider_uses_structured_attribution_without_internal_chunk_ids(evidence):
    def respond(request):
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        assert "[S1]" in payload["messages"][0]["content"]
        assert "a" * 24 not in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "status": "answered",
                                    "blocks": [
                                        {"text": "Digitize 12,000 books.", "sources": ["S1"]}
                                    ],
                                }
                            )
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        model = OpenAIChat("mock", "test-key", client=client)
        result = await model.answer_document(
            [{"role": "user", "content": "whats this plan about"}], evidence
        )
        assert result.supported and "12,000" in result.text
        assert "[source:" + "a" * 24 + "]" in result.text


async def test_document_provider_rejects_wrong_takeaway_count(evidence):
    def respond(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "status": "answered",
                                    "blocks": [{"text": "One point", "sources": ["S1"]}],
                                }
                            )
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        model = OpenAIChat("mock", "test-key", client=client)
        with pytest.raises(GroundingError, match="requested number"):
            await model.answer_document(
                [{"role": "user", "content": "Give me top 5 takeaways from this plan"}], evidence
            )


async def test_document_provider_accepts_source_context_above_the_old_reducer_limit():
    from dataclasses import replace

    evidence = [
        Evidence(
            "a" * 24,
            "doc",
            1,
            "Source requirement. " + "validation " * 100,
            1.0,
            None,
            None,
            None,
            "tenant",
            1,
            "plan.md",
        )
    ]
    evidence = [replace(evidence[0], chunk_id=f"{i:024x}") for i in range(26)]

    def respond(request):
        payload = json.loads(request.content)
        assert "[S26]" in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "status": "answered",
                                    "blocks": [
                                        {
                                            "text": "Source requirements are preserved.",
                                            "sources": ["S26"],
                                        }
                                    ],
                                }
                            )
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        model = OpenAIChat("mock", "test-key", client=client)
        answer = await model.answer_document(
            [{"role": "user", "content": "Summarize this document"}], evidence
        )
        assert answer.supported and f"[source:{25:024x}]" in answer.text


def implementation_plan_payload(count=5):
    return {
        "status": "answered",
        "blocks": [
            {
                "title": f"Phase {i}",
                "actions": ["Prepare the source-defined deliverable."],
                "depends_on": [] if i == 1 else [i - 1],
                "acceptance": ["Verify the deliverable against the source requirements."],
                "sources": ["S1"],
            }
            for i in range(1, count + 1)
        ],
    }


def test_detailed_plan_requires_actions_dependencies_and_acceptance(evidence):
    from agentic_rag.models.grounded import render_implementation_plan

    result = render_implementation_plan(implementation_plan_payload(), evidence)
    assert result.supported
    assert result.text.count("Actions:") == 5
    assert result.text.count("Acceptance checks:") == 5
    assert "Depends on: Phase 4" in result.text


@pytest.mark.parametrize(
    "defect", ["summary_only", "no_actions", "no_acceptance", "forward_dependency"]
)
def test_detailed_plan_rejects_a_synopsis_or_incomplete_phases(evidence, defect):
    from agentic_rag.models.grounded import render_implementation_plan

    data = implementation_plan_payload()
    if defect == "summary_only":
        data = {"status": "answered", "blocks": [{"text": "A cited synopsis", "sources": ["S1"]}]}
    elif defect == "no_actions":
        data["blocks"][0]["actions"] = []
    elif defect == "no_acceptance":
        data["blocks"][0]["acceptance"] = []
    else:
        data["blocks"][0]["depends_on"] = [2]
    with pytest.raises(GroundingError) as failure:
        render_implementation_plan(data, evidence)
    assert failure.value.kind == "format"


async def test_plan_provider_enforces_the_requested_phase_contract(evidence):
    def respond(request):
        payload = json.loads(request.content)
        prompt = payload["messages"][0]["content"].split("SOURCE PASSAGES:")[0]
        assert "depends_on" in prompt
        assert '"text":"your source-backed' not in prompt
        assert payload["max_tokens"] >= 4096
        assert request.extensions["timeout"]["read"] == 60.0
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(implementation_plan_payload())}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        model = OpenAIChat("mock", "test-key", client=client)
        result = await model.answer_document(
            [
                {
                    "role": "user",
                    "content": "Create a detailed implementation plan based on this document",
                }
            ],
            evidence,
        )
        assert result.text.count("Actions:") == 5 and result.text.count("Acceptance checks:") == 5


def test_parenthesized_model_source_labels_become_real_citations(evidence):
    result = render_grounded(
        {
            "status": "answered",
            "blocks": [{"text": "The source defines the deliverable (S1).", "sources": ["S1"]}],
        },
        evidence,
    )
    assert "(S1)" not in result.text and "[source:" in result.text


async def test_truncated_structured_response_is_reported_as_an_output_limit(evidence):
    def respond(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": '{"status":"answered","blocks":['},
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        model = OpenAIChat("mock", "test-key", client=client)
        with pytest.raises(GroundingError, match="output token limit") as error:
            await model.answer_document(
                [
                    {
                        "role": "user",
                        "content": "Create a detailed implementation plan based on this document",
                    }
                ],
                evidence,
            )
        assert error.value.kind == "format"


async def test_semantic_verifier_has_room_for_reasoning_and_reports_completeness(evidence):
    def respond(request):
        payload = json.loads(request.content)
        assert payload["max_tokens"] >= 4096
        assert request.extensions["timeout"]["read"] == 60.0
        assert "task completeness" in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "supported": True,
                                    "complete": False,
                                    "missing": "Add acceptance checks.",
                                    "conflict": False,
                                }
                            )
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        model = OpenAIChat("mock", "test-key", client=client)
        verdict = await model.assess(
            "Create a detailed implementation plan", "A source-backed summary.", evidence
        )
        assert verdict["supported"] is True and verdict["complete"] is False


async def test_verifier_receives_final_passages_without_a_silent_word_window(evidence):
    from dataclasses import replace

    sources = [
        replace(evidence[0], text="x " * 11000),
        replace(
            evidence[0], chunk_id="b" * 24, text="Final acceptance: verify the offline release."
        ),
    ]

    def respond(request):
        payload = json.loads(request.content)
        assert sources[-1].text in payload["messages"][0]["content"]
        assert "[source:" + "b" * 24 + "]" in payload["messages"][0]["content"]
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "supported": True,
                                    "complete": True,
                                    "missing": "",
                                    "conflict": False,
                                }
                            )
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        verdict = await OpenAIChat("mock", "test-key", client=client).assess(
            "Create a detailed implementation plan", "Verify the offline release.", sources
        )
        assert verdict["supported"] and verdict["complete"]
