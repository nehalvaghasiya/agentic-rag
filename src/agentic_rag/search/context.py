"""Token-bounded evidence-context assembly."""

from agentic_rag.models.evidence import Evidence


class ContextBuilder:
    def assemble(self, evidence: list[Evidence], budget: int = 1800) -> str:
        parts: list[str] = []
        remaining = budget
        for item in evidence:
            words = item.text.split()
            if remaining <= 0:
                break
            part = " ".join(words[:remaining])
            parts.append(f"[source:{item.chunk_id}] {item.title}, p.{item.page or '-'}: {part}")
            remaining -= len(part.split())
        return "\n\n".join(parts)
