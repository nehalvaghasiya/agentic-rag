"""Passage-citation validity, precision and evidence coverage."""


class CitationMetrics:
    def score(
        self, citations: list[str], allowed: set[str] | None, required: set[str] | None = None
    ) -> dict[str, float | None]:
        if allowed is None:
            return {"validity": None, "precision": None, "recall": None}
        # A grounded answer with no citations is not citation-valid.
        valid = float(bool(citations) and all(key in allowed for key in citations))
        precision = sum(c in allowed for c in citations) / len(citations) if citations else 0.0
        recall = len(set(citations) & required) / len(required) if required else None
        return {"validity": valid, "precision": precision, "recall": recall}
