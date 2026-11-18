"""MCP server for the bounded demo corpus; production needs transport auth middleware."""

from __future__ import annotations

from agentic_rag.models.principal import Principal
from agentic_rag.models.query import Query
from agentic_rag.search.service import SearchService


def create_server(search: SearchService, *, demo: bool = False) -> object:
    """Never expose a principal-spoofable MCP endpoint in production."""
    if not demo:
        raise PermissionError("MCP server requires production authentication integration")
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("agentic-rag-demo")
    principal = Principal("demo-user", "demo-tenant")

    @server.tool()
    async def search_docs(query: str, kb_id: str = "demo") -> list[dict[str, str]]:
        """Search read-only demo knowledge documents."""
        hits = await search.search(Query(query, (kb_id,), principal), strategy="hybrid", limit=5)
        return [{"id": e.chunk_id, "text": e.text[:1500]} for e in hits]

    @server.tool()
    async def get_source(evidence_id: str) -> dict[str, str]:
        """Retrieve an authorized, version-checked demo source."""
        found = await search.get([evidence_id], principal)
        return {"text": found[0].text, "title": found[0].title} if found else {}

    return server
