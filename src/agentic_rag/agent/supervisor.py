"""Limited supervisor: choose specialist based on intent and evidence gaps."""

from agentic_rag.models.route import RouteDecision


class Supervisor:
    def next(self, route: RouteDecision, has_evidence: bool, steps: int, max_steps: int) -> str:
        if steps >= max_steps:
            return "finish"
        if route.intent == "structured":
            return "sql"
        if route.intent == "multi" and not has_evidence:
            return "research"
        if not has_evidence:
            return "search"
        return "verify"
