"""Explicit security test outcomes; do not claim unexecuted checks passed."""


class SecurityMetrics:
    def score(self, attempts: list[dict[str, bool]]) -> dict[str, float | None]:
        if not attempts:
            return {
                "tested_attacks": 0.0,
                "unauthorized_access_count": None,
                "attack_block_rate": None,
            }
        leaked = sum(not case["blocked"] for case in attempts)
        return {
            "tested_attacks": float(len(attempts)),
            "unauthorized_access_count": float(leaked),
            "attack_block_rate": (len(attempts) - leaked) / len(attempts),
        }
