"""Deterministically exercise EVERY implemented metric family, without an external model.

Synthetic expected values check metric arithmetic, not semantic RAG accuracy.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from agentic_rag.core.config import Settings
from agentic_rag.core.demo import seed
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.eval.agent import AgentMetrics
from agentic_rag.eval.answer import AnswerMetrics
from agentic_rag.eval.citation import CitationMetrics
from agentic_rag.eval.compare import Comparator
from agentic_rag.eval.cost import CostMetrics
from agentic_rag.eval.ingest import IngestMetrics
from agentic_rag.eval.judge import Judge
from agentic_rag.eval.memory import MemoryMetrics
from agentic_rag.eval.retrieve import RetrievalMetrics
from agentic_rag.eval.route import RouteMetrics
from agentic_rag.eval.security import SecurityMetrics
from agentic_rag.eval.speed import SpeedMetrics
from agentic_rag.eval.tools import ToolMetrics


async def main() -> None:
    runtime = RuntimeFactory(Settings(environment="demo"))
    try:
        root = Path(__file__).resolve().parents[1]
        await seed(runtime, root / "datasets" / "demo")
        output = {
            "label": "SYNTHETIC METRIC ARITHMETIC DRY RUN — NOT MODEL QUALITY",
            "retrieval": RetrievalMetrics().score(["relevant", "other"], {"relevant"}, k=2),
            "generation": {
                "token_f1": AnswerMetrics().token_f1("Saturn has rings", "Saturn rings"),
                "fact_coverage": AnswerMetrics().fact_coverage(
                    "Saturn has rings", ["Saturn", "rings"]
                ),
                "abstention_accuracy": AnswerMetrics().abstention("I cannot answer", True),
            },
            "citations": CitationMetrics().score(["one"], {"one", "two"}, {"one"}),
            "tools": ToolMetrics().score(["search", "lookup"], {"search"}, 2, 2),
            "agent": AgentMetrics().score(
                [{"type": "tool_started"}, {"type": "tool_finished"}],
                3,
                completed=True,
                supported=True,
            ),
            "routing": RouteMetrics().score(["baseline", "agentic"], ["baseline", "baseline"]),
            "memory": MemoryMetrics().score([True, False, True]),
            "ingestion": IngestMetrics().score(runtime.store),
            "security": SecurityMetrics().score([{"blocked": True}, {"blocked": False}]),
            "performance": SpeedMetrics().score([10.0, 20.0, 30.0, 40.0]),
            "cost": {
                "known_cost_per_request": CostMetrics().per_request([0.01, 0.03]),
                "unknown_cost": CostMetrics().per_request([0.01, None]),
                "known_cost_per_success": CostMetrics().per_success([0.01, 0.03], 1),
            },
            "llm_judge": await Judge(enabled=False).grade("q", "answer", []),
            "comparison": Comparator().paired_delta([0.3, 0.5], [0.6, 0.7]),
        }
        assert output["retrieval"]["recall"] == 1.0
        assert output["generation"]["fact_coverage"] == 1.0
        assert output["citations"]["validity"] == 1.0
        assert output["tools"]["selection_precision"] == 0.5
        assert output["agent"]["tool_budget_compliance"] == 1.0
        assert output["routing"]["accuracy"] == 0.5
        assert abs(output["memory"]["memory_policy_compliance"] - 2 / 3) < 1e-9
        assert output["ingestion"]["parse_success_rate"] == 1.0
        assert output["security"]["unauthorized_access_count"] == 1.0
        assert output["performance"]["latency_p95_ms"] == 38.5
        assert output["cost"]["unknown_cost"] is None
        assert output["llm_judge"]["correctness"] is None
        path = root / "reports" / "demo" / "all_metrics.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output, indent=2), encoding="utf-8")
        print(f"All 13 metric families exercised: {path}")
    finally:
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())
