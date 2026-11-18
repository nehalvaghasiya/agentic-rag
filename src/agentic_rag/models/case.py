"""Case domain model."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    question: str
    answer: str
    relevant_ids: tuple[str, ...] = ()
    expected_tools: tuple[str, ...] = ()
    expected_mode: str | None = None
    answerable: bool = True
    category: str = "single"
    kb_ids: tuple[str, ...] = ("demo",)
    metadata: dict[str, str] = field(default_factory=dict)
