"""Resolve an individual evidence id with authorization rechecking."""

from agentic_rag.models.result import ToolResult
from agentic_rag.models.tool import ToolSpec
from agentic_rag.search.service import SearchService
from agentic_rag.tools.base import ToolContext


class LookupTool:
    def __init__(self, search: SearchService) -> None:
        self.search = search

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            "lookup",
            "Look up an authorized passage ID",
            {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]},
        )

    async def invoke(self, arguments: dict[str, object], context: ToolContext) -> ToolResult:
        hits = await self.search.get([str(arguments["id"])], context.principal)
        scoped = []
        for hit in hits:
            doc = await self.search.store.get_doc(hit.document_id, context.principal)
            if doc.kb_id in context.kb_ids:
                scoped.append(hit)
        hits = scoped
        return ToolResult(
            "lookup", "ok", {"found": bool(hits)}, tuple(item.chunk_id for item in hits)
        )
