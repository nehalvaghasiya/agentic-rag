"""Seed a synthetic corpus and run an actual ingestion→agent→citation flow."""

from __future__ import annotations

from pathlib import Path

from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.models.principal import Principal
from agentic_rag.models.query import Query
from agentic_rag.models.upload import Upload


async def seed(runtime: RuntimeFactory, root: Path) -> None:
    principal = Principal("demo-user", "demo-tenant", frozenset({"admin", "analyst"}))
    if "demo" not in runtime.store.kbs:
        runtime.knowledge.create_kb("Demo Knowledge", principal, "demo")
    for path in sorted(root.glob("*")):
        if path.suffix in {".txt", ".md"}:
            await runtime.knowledge.submit(
                [Upload(path.name, path.read_bytes())], "demo", principal
            )
    while await runtime.worker.once():
        pass


async def run(runtime: RuntimeFactory) -> list[dict[str, object]]:
    principal = Principal("demo-user", "demo-tenant", frozenset({"admin", "analyst"}))
    output = []
    for mode in ("baseline", "advanced", "agentic"):
        answer = await runtime.agent.run(
            Query("Compare the 2025 and 2026 refund windows", ("demo",), principal), mode=mode
        )
        output.append(
            {
                "mode": mode,
                "answer": answer.text,
                "citations": answer.citations,
                "supported": answer.supported,
                "tools": runtime.store.runs[answer.run_id].tool_calls,
            }
        )
    return output
