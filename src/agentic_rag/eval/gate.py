"""CI release thresholds with security failures never averaged away."""


class Gate:
    def __init__(self, thresholds: dict[str, float]) -> None:
        self.thresholds = thresholds

    def check(self, metrics: dict[str, float | None]) -> dict[str, bool]:
        return {
            name: value is not None and value >= floor
            for name, floor in self.thresholds.items()
            for value in [metrics.get(name)]
        }

    def exit_code(self, metrics: dict[str, float | None]) -> int:
        return int(not all(self.check(metrics).values()))
