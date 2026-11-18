"""UTC clock tool; not derived from an LLM's guessed date."""

from datetime import UTC, datetime

from agentic_rag.models.result import ToolResult
from agentic_rag.models.tool import ToolSpec
from agentic_rag.tools.base import ToolContext


class TimeTool:
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            "time", "Current UTC time", {"type": "object", "properties": {}, "required": []}
        )

    async def invoke(self, arguments: dict[str, object], context: ToolContext) -> ToolResult:
        return ToolResult("time", "ok", {"utc": datetime.now(UTC).isoformat()})
