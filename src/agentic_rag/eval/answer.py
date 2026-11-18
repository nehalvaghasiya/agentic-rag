"""Cheap deterministic answer diagnostics, not an LLM judgment of truth."""

import re
from collections import Counter


class AnswerMetrics:
    @staticmethod
    def _tokens(text: str) -> Counter[str]:
        return Counter(re.findall(r"\b\w+\b", text.lower()))

    def token_f1(self, predicted: str, reference: str) -> float | None:
        if not reference.strip():
            return None
        p = self._tokens(predicted)
        r = self._tokens(reference)
        common = sum((p & r).values())
        if not p or not r:
            return 0.0
        return 2 * common / (sum(p.values()) + sum(r.values()))

    def fact_coverage(self, predicted: str, facts: list[str]) -> float | None:
        if not facts:
            return None
        low = predicted.lower()
        return sum(fact.lower() in low for fact in facts) / len(facts)

    def abstention(self, predicted: str, should_abstain: bool | None) -> float | None:
        if should_abstain is None:
            return None
        abstained = predicted.startswith("I cannot")
        return float(abstained == should_abstain)
