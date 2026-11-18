"""Report domain model."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class EvalReport:
    run_id: str
    dataset: str
    modes: dict[str, dict[str, float | None]]
    cases: tuple[dict[str, object], ...]
    metadata: dict[str, object] = field(default_factory=dict)
