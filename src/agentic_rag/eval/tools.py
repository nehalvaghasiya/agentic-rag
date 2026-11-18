"""Tool selection and execution metrics from recorded real call events."""


class ToolMetrics:
    def score(
        self,
        observed: list[str],
        expected: set[str] | None,
        success: int | None = None,
        attempts: int | None = None,
    ) -> dict[str, float | None]:
        chosen = set(observed)
        if expected is None:
            precision = recall = f1 = None
        else:
            hits = len(chosen & expected)
            precision = hits / len(chosen) if chosen else float(not expected)
            recall = hits / len(expected) if expected else float(not chosen)
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return {
            "selection_precision": precision,
            "selection_recall": recall,
            "selection_f1": f1,
            "success_rate": success / attempts if attempts and success is not None else None,
            "call_count": float(attempts) if attempts is not None else None,
        }
