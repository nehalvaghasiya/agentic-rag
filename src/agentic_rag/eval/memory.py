"""Memory consent and scope test metrics only when scenarios run."""


class MemoryMetrics:
    def score(self, checks: list[bool]) -> dict[str, float | None]:
        return {
            "memory_policy_compliance": sum(checks) / len(checks) if checks else None,
            "memory_checks": float(len(checks)),
        }
