"""Deterministic retrieval metrics with correct label-free missing semantics."""

import math


class RetrievalMetrics:
    def score(
        self,
        ranked: list[str],
        relevant: set[str] | None,
        k: int = 5,
        grades: dict[str, int] | None = None,
    ) -> dict[str, float | None]:
        names = ("precision", "recall", "hit_rate", "mrr", "map", "ndcg")
        if relevant is None or k <= 0:
            return {name: None for name in names}
        seen: set[str] = set()
        unique = []
        for item in ranked:
            if item not in seen:
                unique.append(item)
                seen.add(item)
        ranked = unique[:k]
        hits = [int(uid in relevant) for uid in ranked]
        total = sum(hits)
        reciprocal = next((1.0 / (i + 1) for i, h in enumerate(hits) if h), 0.0)
        average = (
            (
                sum(sum(hits[: i + 1]) / (i + 1) for i, h in enumerate(hits) if h)
                / min(len(relevant), k)
            )
            if relevant
            else 0.0
        )
        grades = grades or {item: 1 for item in relevant}

        def gain(relevance: int) -> int:
            return (1 << relevance) - 1

        dcg = sum(gain(grades.get(uid, 0)) / math.log2(i + 2) for i, uid in enumerate(ranked))
        ideal = sorted((gain(g) for g in grades.values()), reverse=True)[:k]
        idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
        return {
            "precision": total / k,
            "recall": total / len(relevant) if relevant else 0.0,
            "hit_rate": float(total > 0),
            "mrr": reciprocal,
            "map": average,
            "ndcg": dcg / idcg if idcg else 0.0,
        }
