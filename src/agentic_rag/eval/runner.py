"""Single benchmark entrypoint: compare the SAME corpus/model over all execution modes."""

from __future__ import annotations

import statistics
from pathlib import Path
from uuid import uuid4

from agentic_rag.agent.service import AgentService
from agentic_rag.data.repository import Repository
from agentic_rag.eval.agent import AgentMetrics
from agentic_rag.eval.answer import AnswerMetrics
from agentic_rag.eval.citation import CitationMetrics
from agentic_rag.eval.dataset import DatasetLoader
from agentic_rag.eval.memory import MemoryMetrics
from agentic_rag.eval.retrieve import RetrievalMetrics
from agentic_rag.eval.route import RouteMetrics
from agentic_rag.eval.security import SecurityMetrics
from agentic_rag.eval.speed import SpeedMetrics
from agentic_rag.eval.tools import ToolMetrics
from agentic_rag.models.budget import Budget
from agentic_rag.models.principal import Principal
from agentic_rag.models.query import Query
from agentic_rag.models.report import EvalReport


class EvalRunner:
    """Collect per-case outputs, metrics and full traces, without benchmark-only answer shortcuts."""

    def __init__(self, agent: AgentService, store: Repository) -> None:
        self.agent = agent
        self.store = store

    async def run(
        self, dataset: Path, modes: list[str] | None = None, principal: Principal | None = None
    ) -> EvalReport:
        principal = principal or Principal("demo-user", "demo-tenant", frozenset({"analyst"}))
        cases = DatasetLoader().load(dataset)
        modes = modes or ["baseline", "advanced", "agentic"]
        rows: list[dict[str, object]] = []
        summary: dict[str, dict[str, float | None]] = {}
        valid_modes = {"baseline", "advanced", "agentic"}
        if not cases or not set(modes).issubset(valid_modes):
            raise ValueError("Invalid comparison dataset or modes")
        for mode in modes:
            per_metric: dict[str, list[float]] = {}
            elapsed: list[float] = []
            predictions: list[str] = []
            labels: list[str] = []
            for case in cases:
                query = Query(case.question, case.kb_ids, principal)
                try:
                    answer = await self.agent.run(query, mode=mode, budget=Budget())
                    run = await self.store.get_run(answer.run_id, principal)
                    evidence = await self.store.evidence(list(answer.evidence), principal)
                    ranked_titles = [ev.title for ev in evidence]
                    relevant = set(case.relevant_ids)
                    retrieved = RetrievalMetrics().score(ranked_titles, relevant)
                    citation_set = {ev.chunk_id for ev in evidence}
                    citation = CitationMetrics().score(list(answer.citations), citation_set)
                    ans = AnswerMetrics()
                    events = [
                        {"type": e.type, **e.data}
                        for e in await self.store.events(answer.run_id, principal)
                    ]
                    actual_tools = [str(e["name"]) for e in events if e["type"] == "tool_started"]
                    actual_succeeded = sum(
                        e.get("status") == "ok" for e in events if e["type"] == "tool_finished"
                    )
                    tool = ToolMetrics().score(
                        actual_tools,
                        set(case.expected_tools) if mode == "agentic" else None,
                        actual_succeeded,
                        len(actual_tools),
                    )
                    agent = AgentMetrics().score(
                        events, Budget().max_tool_calls, run.status == "completed", answer.supported
                    )
                    route_pred = self.agent.router.route(case.question).mode
                    predictions.append(route_pred)
                    labels.append(case.expected_mode or "baseline")
                    score: dict[str, float | None] = {
                        **{f"retrieval_{key}": value for key, value in retrieved.items()},
                        **{f"citation_{key}": value for key, value in citation.items()},
                        **{f"tool_{key}": value for key, value in tool.items()},
                        **{f"agent_{key}": value for key, value in agent.items()},
                        "answer_token_f1": ans.token_f1(answer.text, case.answer),
                        "abstention_accuracy": ans.abstention(answer.text, not case.answerable),
                        "task_success": float(
                            answer.supported if case.answerable else not answer.supported
                        ),
                        "latency_ms": run.latency_ms,
                    }
                    elapsed.append(run.latency_ms)
                    rows.append(
                        {
                            "case_id": case.id,
                            "category": case.category,
                            "mode": mode,
                            "question": case.question,
                            "answer": answer.text,
                            "evidence_ids": answer.evidence,
                            "citation_ids": answer.citations,
                            "tools": actual_tools,
                            "supported": answer.supported,
                            "scores": score,
                            "events": events,
                        }
                    )
                    for key, value in score.items():
                        if value is not None:
                            per_metric.setdefault(key, []).append(value)
                except Exception as exc:
                    rows.append(
                        {
                            "case_id": case.id,
                            "mode": mode,
                            "error": type(exc).__name__,
                            "scores": {"task_success": 0.0},
                        }
                    )
                    per_metric.setdefault("task_success", []).append(0.0)
                    predictions.append(self.agent.router.route(case.question).mode)
                    labels.append(case.expected_mode or "baseline")
            summary[mode] = {key: statistics.mean(vals) for key, vals in per_metric.items()}
            summary[mode].update(SpeedMetrics().score(elapsed))
            summary[mode]["route_accuracy"] = RouteMetrics().score(predictions, labels)["accuracy"]  # type: ignore[assignment]
            summary[mode]["cost_usd_per_request"] = None
            summary[mode]["judge_faithfulness"] = None
        return EvalReport(
            uuid4().hex,
            str(dataset),
            summary,
            tuple(rows),
            {
                "provider": type(self.agent.chat).__name__,
                "storage": type(self.store).__name__,
                "test_type": "deterministic_offline",
                "ingestion": await self.store.ingest_metrics(principal),
                "memory_policy": MemoryMetrics().score([]),
                "security_checks": SecurityMetrics().score([]),
            },
        )
