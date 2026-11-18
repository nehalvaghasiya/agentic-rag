"""Quantiles from samples, never approximated from averages."""

import math


class SpeedMetrics:
    def percentile(self, samples: list[float], q: float) -> float | None:
        if not samples or not 0 <= q <= 100:
            return None
        values = sorted(samples)
        position = (len(values) - 1) * q / 100
        low = math.floor(position)
        high = math.ceil(position)
        return (
            values[low] * (high - position) + values[high] * (position - low)
            if low != high
            else values[low]
        )

    def score(self, milliseconds: list[float]) -> dict[str, float | None]:
        return {f"latency_p{q}_ms": self.percentile(milliseconds, q) for q in (50, 95, 99)}
