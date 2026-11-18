"""MCP execution policy: only explicitly configured safe destinations."""

from agentic_rag.models.principal import Principal
from agentic_rag.models.tool import ToolSpec
from agentic_rag.security.tools import ToolPolicy


class McpPolicy:
    def authorize(self, tool: ToolSpec, principal: Principal) -> None:
        ToolPolicy().authorize(tool, principal)
        if tool.risk != "read":
            raise PermissionError("Remote MCP writes disabled")
