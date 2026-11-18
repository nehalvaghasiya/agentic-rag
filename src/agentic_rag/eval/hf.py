"""Evaluate a small externally downloaded RAGBench slice, with explicit proxy labels.

RAGBench `response` is a previously generated answer, NOT human truth. Therefore
reference F1 is reported as similarity only, never as answer correctness.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.eval.answer import AnswerMetrics
from agentic_rag.eval.citation import CitationMetrics
from agentic_rag.models.principal import Principal
from agentic_rag.models.query import Query
from agentic_rag.models.upload import Upload


class HFEvaluator:
    """Run identical cases through all three modes against the supplied RAGBench context."""

    def __init__(self, runtime: RuntimeFactory) -> None:
        self.runtime = runtime

    async def run(self, source: Path, limit: int = 20) -> dict[str, object]:
        if limit < 1 or limit > 200:
            raise ValueError("Sample must contain 1–200 cases")
        if not source.is_file():
            raise FileNotFoundError("Download RAGBench first: make hf")
        principal = Principal("benchmark-user", "benchmark-tenant", frozenset({"admin", "analyst"}))
        rows: list[dict[str, Any]] = []
        with source.open(encoding="utf-8") as reader:
            cases = [json.loads(line) for line in reader if line.strip()][:limit]
        for index, case in enumerate(cases):
            if not isinstance(case.get("documents"), list):
                raise ValueError("RAGBench documents must be a list of strings")
            documents = [doc for doc in case["documents"] if isinstance(doc, str) and doc.strip()]
            if not documents or not case.get("question"):
                continue
            kb_id = f"hf_{index:04d}"
            await self.runtime.knowledge.create_kb(f"Benchmark {index}", principal, kb_id)
            await self.runtime.knowledge.submit(
                [
                    Upload(f"context_{j:03d}.txt", content.encode("utf-8"))
                    for j, content in enumerate(documents)
                ],
                kb_id,
                principal,
            )
            while await self.runtime.worker.once(principal):
                pass
            for mode in ("baseline", "advanced", "agentic"):
                answer = await self.runtime.agent.run(
                    Query(str(case["question"]), (kb_id,), principal), mode=mode
                )
                run = await self.runtime.repo.get_run(answer.run_id, principal)
                metrics = CitationMetrics().score(list(answer.citations), set(answer.evidence))
                rows.append(
                    {
                        "id": str(case.get("id", index)),
                        "mode": mode,
                        "response": answer.text,
                        "supported": answer.supported,
                        "latency_ms": run.latency_ms,
                        "tool_calls": run.tool_calls,
                        "retrieved_passages": len(answer.evidence),
                        "citation_validity": metrics["validity"],
                        "reference_similarity_f1": AnswerMetrics().token_f1(
                            answer.text, str(case.get("answer", ""))
                        )
                        if case.get("answer")
                        else None,
                        "reference_is_ground_truth": False,
                        "published_adherence": case.get("label_adherence"),
                    }
                )
        summaries: dict[str, dict[str, object]] = {}
        for mode in ("baseline", "advanced", "agentic"):
            subset = [row for row in rows if row["mode"] == mode]
            summaries[mode] = {
                "cases": len(subset),
                "latency_mean_ms": statistics.mean(float(r["latency_ms"]) for r in subset)
                if subset
                else None,
                "citations_valid_mean": statistics.mean(
                    float(r["citation_validity"])
                    for r in subset
                    if r["citation_validity"] is not None
                )
                if any(r["citation_validity"] is not None for r in subset)
                else None,
                "reference_similarity_f1_mean": statistics.mean(
                    float(r["reference_similarity_f1"])
                    for r in subset
                    if r["reference_similarity_f1"] is not None
                )
                if any(r["reference_similarity_f1"] is not None for r in subset)
                else None,
                "tool_calls_mean": statistics.mean(float(r["tool_calls"]) for r in subset)
                if subset
                else None,
            }
        return {
            "dataset": "galileo-ai/ragbench:covidqa:test",
            "label_warning": "RAGBench response is generated reference, not a gold answer."
            " Published adherence grades the original response, not our system.",
            "modes": summaries,
            "rows": rows,
        }
