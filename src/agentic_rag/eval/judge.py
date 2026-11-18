"""Optional external judge: disabled by default, never silently invent scores."""

from agentic_rag.models.evidence import Evidence


class Judge:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    async def grade(
        self, question: str, answer: str, evidence: list[Evidence]
    ) -> dict[str, float | None]:
        if not self.enabled:
            return {"correctness": None, "faithfulness": None, "citation_support": None}
        raise RuntimeError("LLM judge requires a configured and calibrated judge provider")
