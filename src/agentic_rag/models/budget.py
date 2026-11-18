"""Budget domain model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Budget:
    max_steps: int = 10
    max_tool_calls: int = 6
    max_retries: int = 2
    max_seconds: float = 90.0
    max_input_tokens: int = 13000
    max_output_tokens: int = 1200
    max_usd: float | None = 0.25

    def __post_init__(self) -> None:
        if (
            min(self.max_steps, self.max_seconds, self.max_input_tokens, self.max_output_tokens)
            <= 0
        ):
            raise ValueError("Budgets must be positive")
        if self.max_tool_calls < 0 or self.max_retries < 0:
            raise ValueError("Budgets must be nonnegative")
