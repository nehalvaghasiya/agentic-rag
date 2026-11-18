"""Typed tool catalog with no runtime tool registration from untrusted documents."""

from agentic_rag.tools.base import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.spec.name in self._tools:
            raise ValueError("Duplicate tool")
        self._tools[tool.spec.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise PermissionError("Tool unavailable")
        return self._tools[name]

    def list(self) -> list[dict[str, object]]:
        return [
            {
                "name": t.spec.name,
                "description": t.spec.description,
                "risk": t.spec.risk,
                "version": t.spec.version,
            }
            for t in self._tools.values()
        ]
