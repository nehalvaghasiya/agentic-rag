"""Authoritative public chat payloads; exported through OpenAPI, including SSE."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, RootModel

Mode = Literal["auto", "direct", "baseline", "advanced", "agentic"]
AnswerStatus = Literal[
    "answered",
    "clarification",
    "insufficient_evidence",
    "citation_error",
    "indexing",
    "no_documents",
    "coverage_limit",
    "verification_failed",
]


class SourceCoverage(BaseModel):
    documents: list[str] = Field(default_factory=list)
    total_chunks: int = 0
    read_chunks: int = 0
    strategy: Literal["none", "lookup", "full_document", "map_reduce", "partial"] = "none"


class Citation(BaseModel):
    id: str
    kind: Literal["document", "tool"] = "document"
    title: str
    excerpt: str = ""
    document_id: str | None = None
    version: int | None = None
    page: int | None = None
    section: str | None = None
    tool: str | None = None
    observed_at: str | None = None
    available: bool = True


class RunRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    kb_ids: list[str] = Field(default_factory=list, max_length=8)
    mode: Mode = "auto"
    session_id: str | None = None
    client_message_id: str | None = Field(default=None, max_length=100)
    model_id: str | None = None


class RunAccepted(BaseModel):
    run_id: str
    status: str
    events_url: str
    assistant_message_id: str | None = None
    user_message_id: str | None = None


class RegenerateRequest(BaseModel):
    client_request_id: str = Field(min_length=1, max_length=100)
    expected_run_id: str = Field(min_length=1, max_length=100)


class SelectVersionRequest(BaseModel):
    run_id: str = Field(min_length=1, max_length=100)
    expected_run_id: str = Field(min_length=1, max_length=100)


class AnswerVersion(BaseModel):
    run_id: str
    status: str
    created_at: str


class SessionRequest(BaseModel):
    title: str = Field(default="New chat", min_length=1, max_length=100)
    kb_ids: list[str] = Field(default_factory=list, max_length=8)


class SessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    kb_ids: list[str] | None = Field(default=None, max_length=8)


class ChatMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    status: str = "completed"
    run_id: str | None = None
    created_at: str
    sources: list[Citation] = Field(default_factory=list)
    answer_status: AnswerStatus = "answered"
    parent_user_message_id: str | None = None
    pending_run_id: str | None = None
    versions: list[AnswerVersion] = Field(default_factory=list)


class SessionResponse(BaseModel):
    id: str
    title: str = "New chat"
    kb_ids: list[str] = Field(default_factory=list)
    messages: list[ChatMessage] = Field(default_factory=list)
    updated_at: str
    active_run_id: str | None = None
    summary: str = ""
    summary_through: str | None = None
    summary_status: Literal["idle", "queued", "running", "completed", "failed"] = "idle"


class RunResponse(BaseModel):
    id: str
    status: str
    mode: str
    requested_mode: str
    session_id: str | None = None
    answer: str = ""
    citations: list[str] = Field(default_factory=list)
    sources: list[Citation] = Field(default_factory=list)
    execution_path: Literal["direct", "rag", "agentic"] = "direct"
    grounding: str = "model"
    route_reason: str = ""
    served_from_cache: bool = False
    origin_run_id: str | None = None
    model: str = ""
    tool_calls: int = 0
    steps: int = 0
    latency_ms: float = 0
    error: str | None = None
    usage: dict[str, object] = Field(default_factory=dict)
    answer_status: AnswerStatus = "answered"
    evidence_count: int = 0
    coverage: SourceCoverage = Field(default_factory=SourceCoverage)
    assistant_message_id: str | None = None
    user_message_id: str | None = None
    regeneration_of_run_id: str | None = None
    requested_model_id: str | None = None


class ActivityData(BaseModel):
    model_config = {"extra": "allow"}
    title: str = ""
    description: str = ""
    parent_id: str | None = None
    execution_path: Literal["direct", "rag", "agentic"] | None = None
    mode: str | None = None
    layer: str | None = None
    status: str | None = None
    name: str | None = None
    activity_id: str | None = None
    origin_run_id: str | None = None
    count: int | None = None
    duration_ms: float | None = None
    goals: list[str] | None = None
    arguments: dict[str, object] | None = None
    output: dict[str, object] | None = None
    coverage: SourceCoverage | None = None
    reason_code: str | None = None


class ActivityEvent(BaseModel):
    id: int
    run_id: str
    timestamp: str
    type: Literal[
        "started",
        "context",
        "route",
        "cache",
        "retrieval_started",
        "retrieval",
        "plan",
        "agent_started",
        "agent_finished",
        "tool_started",
        "tool_finished",
        "tool_denied",
        "generation",
        "verification",
        "budget",
        "retry",
        "escalation",
    ]
    data: ActivityData


class DeltaData(BaseModel):
    token: str


class DeltaEvent(BaseModel):
    id: int
    run_id: str
    timestamp: str
    type: Literal["token"]
    data: DeltaData


class CompleteData(RunResponse):
    supported: bool = False


class CompleteEvent(BaseModel):
    id: int
    run_id: str
    timestamp: str
    type: Literal["complete"]
    data: CompleteData


class FailureData(BaseModel):
    code: str
    message: str
    retryable: bool = True
    correlation_id: str


class FailureEvent(BaseModel):
    id: int
    run_id: str
    timestamp: str
    type: Literal["error", "cancelled"]
    data: FailureData


ExecutionEvent = Annotated[
    ActivityEvent | DeltaEvent | CompleteEvent | FailureEvent, Field(discriminator="type")
]


class ExecutionEnvelope(RootModel[ExecutionEvent]):
    pass


class DocumentResponse(BaseModel):
    id: str
    title: str
    content_type: str
    size: int
    status: str
    version: int
    created_at: str
    updated_at: str = ""
    can_delete: bool = False


class PreviewSection(BaseModel):
    text: str
    page: int | None = None
    section: str | None = None


class DocumentPreviewResponse(BaseModel):
    document_id: str
    version: int
    title: str
    offset: int
    total_characters: int
    next_offset: int | None = None
    sections: list[PreviewSection]


class KnowledgeBaseResponse(BaseModel):
    id: str
    name: str
    embedding_model: str
    documents: list[DocumentResponse] = Field(default_factory=list)
    created_at: str = ""
    can_delete: bool = False
