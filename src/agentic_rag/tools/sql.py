"""Read-only structured-data tool over preapproved dataset, not arbitrary SQL."""

import csv
from collections.abc import Callable
from pathlib import Path

from agentic_rag.models.result import ToolResult
from agentic_rag.models.tool import ToolSpec
from agentic_rag.tools.base import ToolContext


class SqlTool:
    def __init__(self, dataset: Path) -> None:
        self.dataset = dataset

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            "sql",
            "Aggregate all rows for the current tenant in the approved CSV. Supports total, count and average only; date, status and vendor filters are unsupported.",
            {
                "type": "object",
                "properties": {"operation": {"type": "string"}},
                "required": ["operation"],
            },
            scopes=frozenset({"analyst"}),
        )

    async def invoke(self, arguments: dict[str, object], context: ToolContext) -> ToolResult:
        op = str(arguments["operation"])
        if op not in {"total", "count", "average"}:
            raise ValueError("Only predefined read-only operations allowed")
        with self.dataset.open(encoding="utf-8", newline="") as file:
            amounts = [
                float(row["amount"])
                for row in csv.DictReader(file)
                if row["tenant_id"] == context.principal.tenant_id
            ]
        operations: dict[str, Callable[[], float | int | None]] = {
            "total": lambda: sum(amounts),
            "count": lambda: len(amounts),
            "average": lambda: sum(amounts) / len(amounts) if amounts else None,
        }
        value = operations[op]()
        return ToolResult(
            "sql",
            "ok",
            {
                "dataset": self.dataset.name,
                "operation": op,
                "value": value,
                "rows": len(amounts),
            },
        )
