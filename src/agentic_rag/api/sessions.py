"""Per-user durable conversations; model context remains separately bounded."""

from uuid import uuid4

from fastapi import APIRouter, Depends

from agentic_rag.api.contracts import (
    ChatMessage,
    RegenerateRequest,
    RunAccepted,
    SelectVersionRequest,
    SessionRequest,
    SessionResponse,
    SessionUpdate,
)
from agentic_rag.api.deps import get_principal, get_runtime
from agentic_rag.api.runs import launch_run, reconcile
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.data.cache import fingerprint
from agentic_rag.data.repository import ConflictError
from agentic_rag.memory.conversation import now
from agentic_rag.models.principal import Principal
from agentic_rag.models.run import Run

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.post("", status_code=201, response_model=SessionResponse)
async def create(
    payload: SessionRequest | None = None,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, object]:
    values = payload or SessionRequest()
    return await runtime.sessions.create(principal, values.title, values.kb_ids)


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    runtime: RuntimeFactory = Depends(get_runtime), principal: Principal = Depends(get_principal)
) -> list[dict[str, object]]:
    sessions = await runtime.sessions.list_sessions(principal)
    for session in sessions:
        if session.get("active_run_id"):
            await reconcile(
                await runtime.repo.get_run(session["active_run_id"], principal), runtime, principal
            )
    return await runtime.sessions.list_sessions(principal)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, object]:
    session = await runtime.sessions.read(session_id, principal)
    if session.get("active_run_id"):
        await reconcile(
            await runtime.repo.get_run(session["active_run_id"], principal), runtime, principal
        )
    return await runtime.sessions.read(session_id, principal)


@router.patch("/{session_id}", response_model=SessionResponse)
async def update(
    session_id: str,
    payload: SessionUpdate,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, object]:
    return await runtime.sessions.update(
        session_id, principal, payload.model_dump(exclude_unset=True)
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> None:
    session = await runtime.sessions.read(session_id, principal)
    run_ids = {m.get("run_id") for m in session["messages"] if m.get("run_id")}
    run_ids.update(v["run_id"] for m in session["messages"] for v in m.get("versions", []))
    if uid := session.get("active_run_id"):
        if task := runtime.tasks.get(uid):
            task.cancel()
            import asyncio

            await asyncio.gather(task, return_exceptions=True)
    if summary := runtime.tasks.get(f"summary:{session_id}"):
        summary.cancel()
    saver = getattr(runtime.agent.graph, "checkpointer", None)
    if saver:
        for run_id in run_ids:
            await saver.adelete_thread(f"{principal.tenant_id}:{principal.user_id}:{run_id}")
    await runtime.sessions.clear(session_id, principal)


@router.post(
    "/{session_id}/messages/{message_id}/regenerate", status_code=202, response_model=RunAccepted
)
async def regenerate(
    session_id: str,
    message_id: str,
    payload: RegenerateRequest,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, object]:
    session = await runtime.repo.get_session(session_id, principal)
    if session.get("active_run_id"):
        await reconcile(
            await runtime.repo.get_run(session["active_run_id"], principal), runtime, principal
        )
        session = await runtime.repo.get_session(session_id, principal)
    answer = next(
        (m for m in session["messages"] if m["id"] == message_id and m["role"] == "assistant"), None
    )
    if not answer or not any(v["run_id"] == payload.expected_run_id for v in answer["versions"]):
        raise ConflictError("Choose an existing version of this reply")
    user = next(
        (m for m in session["messages"] if m["id"] == answer.get("parent_user_message_id")), None
    )
    if not user:
        raise ConflictError("The original question is unavailable")
    origin = await runtime.repo.get_run(payload.expected_run_id, principal)
    if origin.requested_model_id not in {None, "default", runtime.settings.model}:
        raise ConflictError("The original model is no longer configured")
    for kb in origin.kb_ids:
        await runtime.repo.check_kb(kb, principal)
    run = Run(
        uuid4().hex,
        principal.tenant_id,
        principal.user_id,
        session_id=session_id,
        assistant_message_id=message_id,
        regeneration_of_run_id=payload.expected_run_id,
        client_message_id=payload.client_request_id,
        created_at=now(),
        mode=origin.requested_mode,
        requested_mode=origin.requested_mode,
        requested_model_id=origin.requested_model_id,
        kb_ids=origin.kb_ids,
    )
    digest = fingerprint(["regenerate", session_id, message_id, payload.expected_run_id])
    run, created = await runtime.repo.begin_run(run, None, digest, principal)
    if created:
        launch_run(run, user["content"], runtime, principal)
    return {
        "run_id": run.id,
        "status": "accepted" if created else run.status,
        "events_url": f"/api/v2/runs/{run.id}/events",
        "assistant_message_id": run.assistant_message_id,
        "user_message_id": run.user_message_id,
    }


@router.patch("/{session_id}/messages/{message_id}/version", response_model=ChatMessage)
async def select_version(
    session_id: str,
    message_id: str,
    payload: SelectVersionRequest,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, object]:
    await runtime.repo.select_version(
        session_id, message_id, payload.run_id, payload.expected_run_id, principal
    )
    session = await runtime.sessions.read(session_id, principal)
    return next(m for m in session["messages"] if m["id"] == message_id)
