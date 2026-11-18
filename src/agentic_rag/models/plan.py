"""Plan domain model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Plan:
    goals: tuple[str, ...]
    skill: str = "lookup"
