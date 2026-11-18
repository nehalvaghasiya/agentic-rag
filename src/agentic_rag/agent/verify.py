"""Guard against unsupported or revoked citations before serving an answer."""

import re

from agentic_rag.models.evidence import Evidence
from agentic_rag.models.principal import Principal
from agentic_rag.search.citation import CitationValidator


class VerifyAgent:
    def __init__(self, validator: CitationValidator) -> None:
        self.validator = validator

    async def check(
        self, text: str, evidence: list[Evidence], principal: Principal
    ) -> tuple[bool, tuple[str, ...]]:
        citations = tuple(dict.fromkeys(re.findall(r"\[source:([a-f0-9]{24})\]", text)))
        allowed = {e.chunk_id for e in evidence}
        if not citations or any(cid not in allowed for cid in citations):
            return False, ()
        return await self.validator.valid(list(citations), principal), citations
