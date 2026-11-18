"""Real MCP stdio discovery/invocation when the official SDK is installed.

Remote servers must be explicitly configured by operators, never by retrieved text.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any

from agentic_rag.mcp.catalog import McpCatalog
from agentic_rag.models.tool import ToolSpec


class McpClient:
    def __init__(self, command: str, args: list[str], allowlist: set[str]) -> None:
        if command not in {"python", "python3", "uv", "node", "npx"}:
            raise PermissionError("MCP executable is not allowlisted")
        self.command = command
        self.args = args
        self.catalog = McpCatalog(allowlist)
        self.stack = AsyncExitStack()
        self.session: Any = None

    async def connect(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        transport = await self.stack.enter_async_context(
            stdio_client(StdioServerParameters(command=self.command, args=self.args, env=None))
        )
        reader, writer = transport
        session: Any = ClientSession(reader, writer)
        self.session = await self.stack.enter_async_context(session)
        await self.session.initialize()

    async def discover(self) -> list[ToolSpec]:
        if self.session is None:
            raise RuntimeError("MCP not connected")
        response = await self.session.list_tools()
        tools = [
            ToolSpec(tool.name, tool.description or "", tool.inputSchema) for tool in response.tools
        ]
        return self.catalog.allowed_tools(tools)

    async def invoke(self, name: str, arguments: dict[str, object]) -> dict[str, object]:
        allowed = {t.name for t in await self.discover()}
        if name not in allowed:
            raise PermissionError("MCP tool unavailable")
        result = await self.session.call_tool(name, arguments)
        if result.isError:
            raise RuntimeError("MCP tool failed")
        content = [str(item.text)[:4000] for item in result.content if hasattr(item, "text")]
        return {"content": content[:10]}

    async def close(self) -> None:
        await self.stack.aclose()
