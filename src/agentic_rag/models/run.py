"""Run domain model."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class Run:
    id: str
    tenant_id: str
    user_id: str
    status: str = "pending"
    mode: str = "auto"
    answer: str = ""
    citations: list[str] = field(default_factory=list)
    session_id: str | None = None
    tool_calls: int = 0
    steps: int = 0
    latency_ms: float = 0.0
    error: str | None = None
    requested_mode: str = "auto"
    execution_path: str = "direct"
    grounding: str = "model"
    sources: list[dict[str, object]] = field(default_factory=list)
    route_reason: str = ""
    served_from_cache: bool = False
    origin_run_id: str | None = None
    client_message_id: str | None = None
    model: str = ""
    created_at: str = ""
    usage: dict[str, object] = field(default_factory=dict)
    kb_ids: list[str] = field(default_factory=list)
    answer_status: str = "answered"
    evidence_count: int = 0
    coverage: dict[str, object] = field(default_factory=dict)
    assistant_message_id: str | None = None
    user_message_id: str | None = None
    regeneration_of_run_id: str | None = None
    requested_model_id: str | None = None
