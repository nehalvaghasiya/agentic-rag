"""Small bounded evidence-seeking plan, not an unrestricted chain of thought."""

import re

from agentic_rag.models.plan import Plan


class Planner:
    def plan(self, text: str, max_goals: int = 3) -> Plan:
        terms = re.split(r"\s+(?:and|versus|vs\.?|compared to)\s+", text, flags=re.I)
        goals = tuple(term.strip(" ?.\n") for term in terms if term.strip())[:max_goals]
        low = text.lower()
        skill = (
            "sql"
            if "invoice" in low or "revenue" in low
            else "calculate"
            if "calculate" in low
            else "time"
            if "utc" in low or "current time" in low
            else "listing"
            if "all documents" in low
            else "research"
            if len(goals) > 1
            else "lookup"
        )
        return Plan(goals or (text,), skill)
