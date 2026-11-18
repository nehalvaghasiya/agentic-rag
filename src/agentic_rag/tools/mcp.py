"""MCP remote call wrapped as a typed read-only agent tool."""

from agentic_rag.mcp.client import McpClient
from agentic_rag.models.result import ToolResult
from agentic_rag.models.tool import ToolSpec
from agentic_rag.tools.base import ToolContext


class McpTool:
    def __init__(self, client: McpClient, name: str) -> None:
        self.client = client
        self.name = name

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            self.name,
            "Trusted remote MCP read-only tool",
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        )

    async def invoke(self, arguments: dict[str, object], context: ToolContext) -> ToolResult:
        result = await self.client.invoke(self.name, arguments)
        return ToolResult(self.name, "ok", result)
