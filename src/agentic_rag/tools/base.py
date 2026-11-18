"""Typed execution boundary shared by built-in and MCP tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from agentic_rag.models.principal import Principal
from agentic_rag.models.result import ToolResult
from agentic_rag.models.tool import ToolSpec


@dataclass(frozen=True, slots=True)
class ToolContext:
    principal: Principal
    run_id: str
    kb_ids: tuple[str, ...]
    parent_id: str | None = None


class Tool(Protocol):
    @property
    def spec(self) -> ToolSpec: ...
    async def invoke(self, arguments: dict[str, object], context: ToolContext) -> ToolResult: ...
