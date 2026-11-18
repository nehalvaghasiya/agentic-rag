"""Usage domain model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    usd: float | None = None
