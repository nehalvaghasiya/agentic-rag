"""Route domain model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RouteDecision:
    mode: str
    intent: str
    confidence: float
    reason: str
