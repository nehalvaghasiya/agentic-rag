"""Numeric correctness and missing-label semantics of all deterministic metrics."""

import pytest

from agentic_rag.eval.agent import AgentMetrics
from agentic_rag.eval.answer import AnswerMetrics
from agentic_rag.eval.citation import CitationMetrics
from agentic_rag.eval.compare import Comparator
from agentic_rag.eval.cost import CostMetrics
from agentic_rag.eval.gate import Gate
from agentic_rag.eval.memory import MemoryMetrics
from agentic_rag.eval.retrieve import RetrievalMetrics
from agentic_rag.eval.route import RouteMetrics
from agentic_rag.eval.security import SecurityMetrics
from agentic_rag.eval.speed import SpeedMetrics
from agentic_rag.eval.tools import ToolMetrics


def test_retrieval_metrics() -> None:
    x = RetrievalMetrics().score(["a", "x", "b"], {"a", "b"}, k=3)
    assert x["precision"] == pytest.approx(2 / 3)
    assert x["recall"] == 1.0
    assert x["mrr"] == 1.0
    assert x["hit_rate"] == 1.0
    assert x["map"] == pytest.approx((1 + 2 / 3) / 2)
    assert x["ndcg"] == pytest.approx(1 / 1.0 * x["ndcg"])
    assert RetrievalMetrics().score(["a"], None)["mrr"] is None
    assert RetrievalMetrics().score([], {"a"})["ndcg"] == 0
    assert RetrievalMetrics().score(["a", "a"], {"a"})["recall"] == 1


def test_answers_and_citations() -> None:
    metrics = AnswerMetrics()
    assert metrics.token_f1("abc def", "abc def") == 1
    assert metrics.token_f1("none", "abc") == 0
    assert metrics.token_f1("x", "") is None
    assert metrics.abstention("I cannot verify", True) == 1
    assert metrics.fact_coverage("14 days, 30 days", ["14 days", "30 days"]) == 1
    assert CitationMetrics().score(["x", "wrong"], {"x"}, {"x"}) == {
        "validity": 0.0,
        "precision": 0.5,
        "recall": 1.0,
    }
    assert CitationMetrics().score([], {"x"})["validity"] == 0


def test_agent_and_tools() -> None:
    x = ToolMetrics().score(["search", "sql"], {"search"}, success=1, attempts=2)
    assert x["selection_precision"] == 0.5
    assert x["selection_recall"] == 1
    assert x["selection_f1"] == pytest.approx(2 / 3)
    a = AgentMetrics().score([{"type": "tool_started"}] * 3, 2, True, True)
    assert a["tool_budget_compliance"] == 0
    assert RouteMetrics().score(["a", "b"], ["a", "a"])["accuracy"] == 0.5


def test_speed_cost_and_nulls() -> None:
    assert SpeedMetrics().percentile([1, 2, 3, 4], 50) == 2.5
    assert SpeedMetrics().percentile([], 95) is None
    assert CostMetrics().per_request([None, 1]) is None
    assert CostMetrics().per_success([0.5, 0.5], 2) == 0.5
    assert MemoryMetrics().score([])["memory_policy_compliance"] is None
    assert SecurityMetrics().score([])["unauthorized_access_count"] is None
    assert SecurityMetrics().score([{"blocked": True}])["attack_block_rate"] == 1
    assert Comparator().paired_delta([0, 1, 2], [1, 2, 3])["delta"] == 1
    assert Gate({"recall": 0.8}).exit_code({"recall": 0.7}) == 1
    assert Gate({"recall": 0.8}).exit_code({"recall": 0.9}) == 0
