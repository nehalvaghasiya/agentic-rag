"""Provider-billed costs; unknown cost must remain null, not zero."""


class CostMetrics:
    def per_request(self, prices: list[float | None]) -> float | None:
        if not prices or any(x is None for x in prices):
            return None
        return sum(x for x in prices if x is not None) / len(prices)

    def per_success(self, prices: list[float | None], success_count: int) -> float | None:
        if not prices or success_count <= 0 or any(x is None for x in prices):
            return None
        return sum(x for x in prices if x is not None) / success_count
