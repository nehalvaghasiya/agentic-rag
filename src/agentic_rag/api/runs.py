"""Durable run creation, idempotency, cancellation, source checks and SSE replay."""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import asdict
from uuid import uuid4

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse

from agentic_rag.api.contracts import (
    ExecutionEnvelope,
    RunAccepted,
    RunRequest,
    RunResponse,
)
from agentic_rag.api.deps import get_principal, get_runtime
from agentic_rag.api.sse import format_event, parse_last_event_id
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.data.cache import fingerprint
from agentic_rag.memory.conversation import now
from agentic_rag.models.event import Event
from agentic_rag.models.principal import Principal
from agentic_rag.models.query import Query
from agentic_rag.models.run import Run

router = APIRouter(prefix="/runs", tags=["Chat runs"])


async def reconcile(run: Run, runtime: RuntimeFactory, p: Principal) -> Run:
    if run.status in {"pending", "running"} and run.id not in runtime.tasks:
        run.status, run.error, run.answer = (
            "failed",
            "RUN_INTERRUPTED",
            "The server restarted before this response finished. Please retry the message.",
        )
        await runtime.repo.finish(
            run,
            "error",
            {
                "code": "RUN_INTERRUPTED",
                "message": "The server restarted before this response finished. Please retry the message.",
                "retryable": True,
                "correlation_id": run.id,
                "finished_at": now(),
            },
            p,
        )
    return run


async def public_run(run: Run, runtime: RuntimeFactory, p: Principal) -> dict[str, object]:
    sources = await runtime.sessions.sanitize_sources(run.sources, p)
    data = asdict(run)
    data["sources"] = sources
    if run.answer.startswith("I cannot verify an answer from the available authorized sources."):
        data["answer_status"] = "insufficient_evidence"
    if any(not s.get("available", True) for s in sources):
        data["answer"] = "This answer used a source that is no longer available."
    return data


def launch_run(run: Run, question: str, runtime: RuntimeFactory, principal: Principal) -> None:
    query = Query(question, tuple(run.kb_ids), principal, run.session_id)

    async def execute() -> None:
        begin = time.monotonic()
        try:
            answer = await runtime.agent.run(query, mode=run.requested_mode, run_id=run.id)
            runtime.metrics.observe(answer.mode, "ok", time.monotonic() - begin)
            if run.session_id:

                async def summarize() -> None:
                    assert run.session_id is not None
                    try:
                        await runtime.sessions.summarize(run.session_id, principal)
                    except Exception:
                        # A failed summary cannot invalidate an already completed response.
                        pass

                key = f"summary:{run.session_id}"
                if key not in runtime.tasks:
                    task = asyncio.create_task(summarize())
                    runtime.tasks[key] = task
                    task.add_done_callback(lambda _: runtime.tasks.pop(key, None))
        except (Exception, asyncio.CancelledError) as error:
            runtime.metrics.observe(run.requested_mode, "error", time.monotonic() - begin)
            if not isinstance(error, asyncio.CancelledError):
                logging.getLogger(__name__).exception("Chat run %s failed", run.id)
            try:
                current = await runtime.repo.get_run(run.id, principal)
                if current.status in {"pending", "running"}:
                    current.status, current.error = "failed", type(error).__name__
                    current.answer = (
                        "The response could not be completed. You can retry this message."
                    )
                    await runtime.repo.finish(
                        current,
                        "error",
                        {
                            "code": "RUN_FAILED",
                            "message": current.answer,
                            "retryable": True,
                            "correlation_id": run.id,
                            "finished_at": now(),
                        },
                        principal,
                    )
            except PermissionError:
                pass  # A deleted chat intentionally removed its run.

    task = asyncio.create_task(execute())
    runtime.tasks[run.id] = task
    task.add_done_callback(lambda _: runtime.tasks.pop(run.id, None))


@router.post("", status_code=202, response_model=RunAccepted)
async def start_run(
    payload: RunRequest,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, object]:
    if not payload.question.strip():
        raise ValueError("Question cannot be empty")
    if payload.model_id not in {None, "default", runtime.settings.model}:
        raise ValueError("Choose a server-configured model")
    for kb in payload.kb_ids:
        await runtime.repo.check_kb(kb, principal)
    if payload.session_id:
        session = await runtime.repo.get_session(payload.session_id, principal)
        if session.get("active_run_id"):
            await reconcile(
                await runtime.repo.get_run(session["active_run_id"], principal), runtime, principal
            )
    run_id = uuid4().hex
    run = Run(
        run_id,
        principal.tenant_id,
        principal.user_id,
        mode=payload.mode,
        requested_mode=payload.mode,
        session_id=payload.session_id,
        client_message_id=payload.client_message_id,
        created_at=now(),
        kb_ids=payload.kb_ids,
        requested_model_id=runtime.settings.model,
    )
    message = (
        {
            "id": uuid4().hex,
            "role": "user",
            "content": payload.question,
            "status": "completed",
            "run_id": run_id,
            "created_at": run.created_at,
            "sources": [],
        }
        if payload.session_id
        else None
    )
    digest = fingerprint(
        [payload.question, payload.kb_ids, payload.mode, payload.session_id, payload.model_id]
    )
    run, created = await runtime.repo.begin_run(run, message, digest, principal)
    if created:
        launch_run(run, payload.question, runtime, principal)
    return {
        "run_id": run.id,
        "status": "accepted" if created else run.status,
        "events_url": f"/api/v2/runs/{run.id}/events",
        "assistant_message_id": run.assistant_message_id,
        "user_message_id": run.user_message_id,
    }


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, object]:
    run = await reconcile(await runtime.repo.get_run(run_id, principal), runtime, principal)
    return await public_run(run, runtime, principal)


@router.post("/{run_id}/cancel")
async def cancel(
    run_id: str,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, str]:
    await runtime.agent.cancel(run_id, principal)
    if task := runtime.tasks.get(run_id):
        task.cancel()
    return {"status": "cancelled"}


@router.get(
    "/{run_id}/events",
    responses={200: {"content": {"text/event-stream": {"schema": {"type": "string"}}}}},
)
async def events(
    run_id: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> StreamingResponse:
    await reconcile(await runtime.repo.get_run(run_id, principal), runtime, principal)
    cursor = parse_last_event_id(last_event_id)

    async def stream() -> AsyncIterator[str]:
        nonlocal cursor
        while True:
            for event in await runtime.repo.events(run_id, principal, cursor):
                cursor = event.id
                if event.type == "complete":
                    run = await runtime.repo.get_run(run_id, principal)
                    safe = await public_run(run, runtime, principal)
                    event.data.update(safe)
                validated = ExecutionEnvelope.model_validate(asdict(event)).root.model_dump()
                yield format_event(
                    Event(event.id, event.run_id, event.type, validated["data"], event.timestamp)
                )
                if event.type in {"complete", "error", "cancelled"}:
                    return
            run = await runtime.repo.get_run(run_id, principal)
            if run.status in {"completed", "failed", "cancelled"}:
                return
            yield ": heartbeat\n\n"
            await asyncio.sleep(0.1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )


# The event union is part of OpenAPI even though SSE itself is a framed byte stream.
@router.get("/{run_id}/activity", response_model=list[ExecutionEnvelope])
async def activity(
    run_id: str,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> list[dict[str, object]]:
    run = await runtime.repo.get_run(run_id, principal)
    items = await runtime.repo.events(run_id, principal)
    safe = await public_run(run, runtime, principal)
    return [
        {**asdict(e), "data": {**e.data, **safe} if e.type == "complete" else e.data} for e in items
    ]
