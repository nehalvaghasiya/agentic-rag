"""Reproducible paired bootstrap confidence interval for mode comparisons."""

import random


def bootstrap_ci(
    pairs: list[tuple[float, float]], iterations: int = 500, seed: int = 42
) -> tuple[float, float] | None:
    if not pairs:
        return None
    rng = random.Random(seed)
    delta = [b - a for a, b in pairs]
    estimates = sorted(
        sum(rng.choices(delta, k=len(delta))) / len(delta) for _ in range(iterations)
    )
    return estimates[int(0.025 * (iterations - 1))], estimates[int(0.975 * (iterations - 1))]
