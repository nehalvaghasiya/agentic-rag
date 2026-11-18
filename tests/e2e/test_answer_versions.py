"""Public regeneration, version selection, and recovery behavior."""

import asyncio

import httpx
import pytest

from agentic_rag.api.app import create_app
from agentic_rag.api.deps import get_principal
from agentic_rag.core.config import Settings
from agentic_rag.memory.conversation import now
from agentic_rag.models.principal import Principal
from agentic_rag.models.run import Run


@pytest.fixture
async def api():
    app = create_app(Settings(environment="demo"))
    owner = Principal("version-owner", "versions-tenant", frozenset({"admin", "analyst"}))

    async def identity():
        return owner

    app.dependency_overrides[get_principal] = identity
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, app, owner


async def finish(client, accepted):
    assert accepted.status_code == 202, accepted.text
    uid = accepted.json()["run_id"]
    response = await client.get(f"/api/v2/runs/{uid}/events")
    assert response.status_code == 200
    return (await client.get(f"/api/v2/runs/{uid}")).json()


async def initial(client, question="Hello"):
    session = (await client.post("/api/v2/sessions", json={})).json()
    accepted = await client.post(
        "/api/v2/runs", json={"session_id": session["id"], "question": question}
    )
    run = await finish(client, accepted)
    sid, mid = session["id"], accepted.json()["assistant_message_id"]
    return sid, mid, run


async def test_regeneration_keeps_one_turn_and_selected_context(api, monkeypatch):
    client, app, owner = api
    calls = []

    async def respond(messages):
        calls.append(messages)
        yield f"Answer {len(calls)}"

    monkeypatch.setattr(app.state.runtime.chat, "stream", respond)
    sid, mid, first = await initial(client)
    url = f"/api/v2/sessions/{sid}/messages/{mid}"
    payload = {"client_request_id": "regen-1", "expected_run_id": first["id"]}
    accepted = await client.post(url + "/regenerate", json=payload)
    second = await finish(client, accepted)
    replay = await client.post(url + "/regenerate", json=payload)
    assert replay.json()["run_id"] == second["id"]
    assert second["regeneration_of_run_id"] == first["id"]
    assert second["served_from_cache"] is False
    assert len(calls) == 2
    assert calls[0] == calls[1]  # The old answer and prompt are absent from regeneration history.
    session = (await client.get(f"/api/v2/sessions/{sid}")).json()
    assert len(session["messages"]) == 2
    answer = session["messages"][-1]
    assert answer["id"] == mid and answer["content"] == "Answer 2"
    assert [v["status"] for v in answer["versions"]] == ["completed", "completed"]
    selected = await client.patch(
        url + "/version", json={"run_id": first["id"], "expected_run_id": second["id"]}
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["content"] == "Answer 1"
    history, _ = await app.state.runtime.sessions.context(sid, owner, "next")
    assert history == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Answer 1"},
    ]
    restored = (await client.get(f"/api/v2/sessions/{sid}")).json()
    assert restored["messages"][-1]["run_id"] == first["id"]
    stale = await client.patch(
        url + "/version", json={"run_id": second["id"], "expected_run_id": second["id"]}
    )
    assert stale.status_code == 409
    await finish(
        client,
        await client.post(
            "/api/v2/runs", json={"session_id": sid, "question": "Why is the sky blue?"}
        ),
    )
    blocked = await client.post(
        url + "/regenerate", json={**payload, "client_request_id": "older-reply"}
    )
    assert blocked.status_code == 409
    assert (
        await client.patch(
            url + "/version", json={"run_id": second["id"], "expected_run_id": first["id"]}
        )
    ).status_code == 409
    # An idempotent transport retry remains a replay even after a follow-up exists.
    assert (await client.post(url + "/regenerate", json=payload)).json()["run_id"] == second["id"]


@pytest.mark.parametrize("terminal", ["failed", "cancelled", "interrupted"])
async def test_unsuccessful_regeneration_preserves_prior_answer(api, monkeypatch, terminal):
    client, app, owner = api
    sid, mid, original = await initial(client)
    runtime = app.state.runtime
    entered = asyncio.Event()
    release = asyncio.Event()

    async def respond(messages):
        entered.set()
        await release.wait()
        if terminal == "failed":
            raise RuntimeError("private-failure-sentinel")
        yield "New answer"

    monkeypatch.setattr(runtime.chat, "stream", respond)
    url = f"/api/v2/sessions/{sid}/messages/{mid}"
    accepted = await client.post(
        url + "/regenerate", json={"expected_run_id": original["id"], "client_request_id": terminal}
    )
    assert accepted.status_code == 202
    uid = accepted.json()["run_id"]
    await asyncio.wait_for(entered.wait(), 2)
    pending = (await client.get(f"/api/v2/sessions/{sid}")).json()
    assert len(pending["messages"]) == 2 and pending["active_run_id"] == uid
    assert pending["messages"][-1]["pending_run_id"] == uid
    history, _ = await runtime.sessions.context(sid, owner, uid)
    assert history == []
    conflict = await client.patch(
        url + "/version", json={"run_id": original["id"], "expected_run_id": original["id"]}
    )
    assert conflict.status_code == 409
    if terminal == "failed":
        release.set()
    elif terminal == "cancelled":
        assert (await client.post(f"/api/v2/runs/{uid}/cancel")).status_code == 200
    else:
        task = runtime.tasks.pop(uid)
        # Simulate a lost worker, then reconcile without allowing its callback to overwrite recovery.
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    await client.get(f"/api/v2/runs/{uid}/events")
    restored = (await client.get(f"/api/v2/sessions/{sid}")).json()
    assert restored["active_run_id"] is None
    answer = restored["messages"][-1]
    assert answer["run_id"] == original["id"] and answer["content"] == original["answer"]
    assert answer["versions"][-1]["status"] in {"failed", "cancelled"}
    assert "private-failure-sentinel" not in str(restored)


async def test_versions_are_owned_and_failed_original_can_be_retried(api, monkeypatch):
    client, app, _ = api
    original_stream = app.state.runtime.chat.stream

    async def fail(messages):
        raise RuntimeError("fixture failure")
        yield ""

    monkeypatch.setattr(app.state.runtime.chat, "stream", fail)
    sid, mid, failed = await initial(client)
    assert failed["status"] == "failed"
    monkeypatch.setattr(app.state.runtime.chat, "stream", original_stream)
    retried = await finish(
        client,
        await client.post(
            f"/api/v2/sessions/{sid}/messages/{mid}/regenerate",
            json={"expected_run_id": failed["id"], "client_request_id": "retry-failed"},
        ),
    )
    assert retried["status"] == "completed"

    async def another_user():
        return Principal("another-user", "versions-tenant")

    app.dependency_overrides[get_principal] = another_user
    assert (await client.get(f"/api/v2/runs/{retried['id']}")).status_code == 403
    assert (
        await client.patch(
            f"/api/v2/sessions/{sid}/messages/{mid}/version",
            json={"run_id": failed["id"], "expected_run_id": retried["id"]},
        )
    ).status_code == 403


async def test_orphaned_regeneration_is_reconciled_without_losing_the_selected_answer(api):
    client, app, owner = api
    sid, mid, original = await initial(client)
    run = Run(
        "orphaned-version",
        owner.tenant_id,
        owner.user_id,
        session_id=sid,
        assistant_message_id=mid,
        regeneration_of_run_id=original["id"],
        created_at=now(),
    )
    await app.state.runtime.repo.begin_run(run, None, "orphaned-regeneration", owner)
    restored = (await client.get(f"/api/v2/sessions/{sid}")).json()
    assert restored["active_run_id"] is None
    assert len(restored["messages"]) == 2
    answer = restored["messages"][-1]
    assert answer["run_id"] == original["id"] and answer["content"] == original["answer"]
    assert answer["versions"][-1]["status"] == "failed"
    recovered = (await client.get(f"/api/v2/runs/{run.id}")).json()
    assert recovered["error"] == "RUN_INTERRUPTED"
