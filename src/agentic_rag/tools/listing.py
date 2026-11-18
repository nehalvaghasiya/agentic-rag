"""List only documents the caller is authorized to view."""

from agentic_rag.data.repository import Repository
from agentic_rag.models.result import ToolResult
from agentic_rag.models.tool import ToolSpec
from agentic_rag.tools.base import ToolContext


class ListDocsTool:
    def __init__(self, store: Repository) -> None:
        self.store = store

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            "listing",
            "List available documents",
            {"type": "object", "properties": {}, "required": []},
        )

    async def invoke(self, arguments: dict[str, object], context: ToolContext) -> ToolResult:
        docs = [
            d for kb in context.kb_ids for d in await self.store.list_docs(context.principal, kb)
        ]
        return ToolResult("listing", "ok", {"documents": [d.title for d in docs[:30]]})
