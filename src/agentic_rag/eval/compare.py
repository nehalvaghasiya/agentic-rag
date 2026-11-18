"""Compare paired mode scores without losing failed cases."""

from agentic_rag.eval.stats import bootstrap_ci


class Comparator:
    def paired_delta(self, baseline: list[float], other: list[float]) -> dict[str, object]:
        if len(baseline) != len(other) or not baseline:
            return {"delta": None, "ci95": None}
        pairs = list(zip(baseline, other, strict=True))
        return {"delta": sum(b - a for a, b in pairs) / len(pairs), "ci95": bootstrap_ci(pairs)}
