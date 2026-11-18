"""Allowlist and schema checks for discovered MCP tools."""

from agentic_rag.models.tool import ToolSpec


class McpCatalog:
    def __init__(self, names: set[str]) -> None:
        self.names = names

    def allowed_tools(self, discovered: list[ToolSpec]) -> list[ToolSpec]:
        return [
            tool
            for tool in discovered
            if tool.name in self.names
            and tool.risk == "read"
            and tool.parameters.get("type") == "object"
        ]
