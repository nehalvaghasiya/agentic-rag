"""Actual ASGI request sequence: create, upload, worker, agent, SSE, source, delete."""

import asyncio
import io

import httpx
import pytest

from agentic_rag.api.app import create_app
from agentic_rag.core.config import Settings


async def test_http_ingest_agent_stream_and_source() -> None:
    app = create_app(Settings(environment="demo"))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            ready = await client.get("/api/v2/health/ready")
            assert ready.json()["ephemeral"] is True
            kb = await client.post("/api/v2/kb", json={"name": "API smoke"})
            assert kb.status_code == 201
            kb_id = kb.json()["id"]
            upload = await client.post(
                f"/api/v2/kb/{kb_id}/documents",
                files=[
                    (
                        "files",
                        (
                            "facts.md",
                            io.BytesIO(b"Saturn has beautiful rings. Neptune is an ice giant."),
                            "text/markdown",
                        ),
                    )
                ],
            )
            assert upload.status_code == 202, upload.text
            job_id = upload.json()[0]["id"]
            status = await client.get(f"/api/v2/jobs/{job_id}")
            assert status.json()["status"] == "done"
            run = await client.post(
                "/api/v2/runs",
                json={"question": "What does Saturn have?", "mode": "agentic", "kb_ids": [kb_id]},
            )
            assert run.status_code == 202, run.text
            run_id = run.json()["run_id"]
            for _ in range(40):
                state = (await client.get(f"/api/v2/runs/{run_id}")).json()
                if state["status"] != "pending" and state["status"] != "running":
                    break
                await asyncio.sleep(0.02)
            assert state["status"] == "completed", state
            stream = await client.get(f"/api/v2/runs/{run_id}/events")
            assert stream.status_code == 200
            assert "event: tool_started" in stream.text
            assert "event: complete" in stream.text
            assert "[1]" in state["answer"] and state["sources"]
            cid = state["citations"][0]
            source = await client.get(f"/api/v2/sources/{cid}")
            assert "Saturn" in source.json()["text"]
            result = await client.delete(f"/api/v2/documents/{source.json()['document_id']}")
            assert result.status_code == 204
            assert (await client.get(f"/api/v2/sources/{cid}")).status_code == 403
            assert "rag_requests_total" in (await client.get("/metrics")).text


async def test_session_memory_and_admin_evaluation() -> None:
    app = create_app(Settings(environment="demo"))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            session = (await client.post("/api/v2/sessions")).json()
            assert session["messages"] == []
            mem = await client.get("/api/v2/memory")
            assert mem.status_code == 200 and mem.json() == []
            assert (await client.put("/api/v2/memory/consent", json={"enabled": True})).json()[
                "enabled"
            ]
            assert (
                await client.post("/api/v2/runs", json={"question": "Why", "mode": "wrong"})
            ).status_code == 422
            # Evaluation without a seeded KB is expected to return failed-case diagnostics, not crash.
            metrics = await client.post("/api/v2/admin/evals")
            assert metrics.status_code == 200
            assert metrics.json()["modes"]["baseline"]["task_success"] == 0


def test_production_refuses_fake_store() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings(
            environment="production",
            store="fake",
            provider="openai",
            api_key="x",
            jwt_secret="x" * 48,
        ).validate_runtime()


async def test_unified_chat_http_idempotency_and_sse_replay():
    app = create_app(Settings(environment="demo"))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            session = (await client.post("/api/v2/sessions", json={})).json()
            body = {
                "question": "Hello",
                "session_id": session["id"],
                "client_message_id": "stable-message",
            }
            first = await client.post("/api/v2/runs", json=body)
            second = await client.post("/api/v2/runs", json=body)
            assert first.json()["run_id"] == second.json()["run_id"]
            uid = first.json()["run_id"]
            for _ in range(50):
                run = (await client.get(f"/api/v2/runs/{uid}")).json()
                if run["status"] == "completed":
                    break
                await asyncio.sleep(0.01)
            assert run["mode"] == "direct" and run["answer"].startswith("Hello")
            activity = (await client.get(f"/api/v2/runs/{uid}/activity")).json()
            assert [e["id"] for e in activity] == list(range(1, len(activity) + 1))
            cursor = activity[-2]["id"]
            replay = await client.get(
                f"/api/v2/runs/{uid}/events", headers={"Last-Event-ID": str(cursor)}
            )
            assert "event: complete" in replay.text
            assert f"id: {cursor}\n" not in replay.text
            assert "tenant_id" not in replay.text and "user_id" not in replay.text
            restored = (await client.get(f"/api/v2/sessions/{session['id']}")).json()
            assert len(restored["messages"]) == 2
            conflict = await client.post(
                "/api/v2/runs", json={**body, "question": "Different request"}
            )
            assert conflict.status_code == 409
