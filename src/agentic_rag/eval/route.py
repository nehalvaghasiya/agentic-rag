"""Route accuracy and per-class confusion counts from labeled cases."""

from collections import defaultdict


class RouteMetrics:
    def score(self, predictions: list[str], labels: list[str]) -> dict[str, object]:
        if len(predictions) != len(labels) or not labels:
            return {"accuracy": None, "macro_f1": None, "confusion": {}}
        confusion: dict[str, dict[str, int]] = defaultdict(dict)
        for label, predicted in zip(labels, predictions, strict=True):
            bucket = confusion[label]
            bucket[predicted] = bucket.get(predicted, 0) + 1
        classes = set(labels) | set(predictions)
        f1s = []
        for label in classes:
            tp = sum(a == label and b == label for a, b in zip(labels, predictions, strict=True))
            fp = sum(a != label and b == label for a, b in zip(labels, predictions, strict=True))
            fn = sum(a == label and b != label for a, b in zip(labels, predictions, strict=True))
            f1s.append(2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0)
        return {
            "accuracy": sum(a == b for a, b in zip(labels, predictions, strict=True)) / len(labels),
            "macro_f1": sum(f1s) / len(f1s),
            "confusion": dict(confusion),
        }
