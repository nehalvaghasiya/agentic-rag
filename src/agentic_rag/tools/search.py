"""Authorized hybrid search as a callable agent tool."""

from agentic_rag.models.query import Query
from agentic_rag.models.result import ToolResult
from agentic_rag.models.tool import ToolSpec
from agentic_rag.search.service import SearchService
from agentic_rag.tools.base import ToolContext


class SearchTool:
    def __init__(self, search: SearchService) -> None:
        self.search = search

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            "search",
            "Search authorized knowledge documents",
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        )

    async def invoke(self, arguments: dict[str, object], context: ToolContext) -> ToolResult:
        query = Query(
            str(arguments["query"]),
            context.kb_ids,
            context.principal,
            filters={"run_id": context.run_id},
        )
        hits = await self.search.search(query, strategy="advanced", limit=6)
        return ToolResult(
            "search", "ok", {"hits": len(hits)}, tuple(item.chunk_id for item in hits)
        )
