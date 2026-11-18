"""Answer domain model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Answer:
    text: str
    citations: tuple[str, ...]
    supported: bool
    run_id: str
    mode: str
    evidence: tuple[str, ...] = ()
