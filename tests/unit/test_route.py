"""Adaptive routing must be deterministic and allow manual mode overrides."""

from agentic_rag.agent.plan import Planner
from agentic_rag.agent.route import Router


def test_router_and_plan() -> None:
    r = Router()
    assert r.route("What is the refund window?").mode == "baseline"
    assert r.route("Compare 2025 and 2026").mode == "agentic"
    assert r.route("Invoice count?").intent == "structured"
    assert r.route("Compare 2025 and 2026", "advanced").mode == "advanced"
    assert len(Planner().plan("Compare A and B").goals) == 2
