"""Citation verification against current tenant/ACL/document revision."""

from agentic_rag.models.principal import Principal
from agentic_rag.search.service import SearchService


class CitationValidator:
    def __init__(self, service: SearchService) -> None:
        self.service = service

    async def valid(self, citations: list[str], principal: Principal) -> bool:
        if not citations:
            return False
        found = await self.service.get(citations, principal)
        return set(citations) == {ev.chunk_id for ev in found}
