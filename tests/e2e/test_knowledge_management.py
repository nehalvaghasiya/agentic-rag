"""Knowledge management through real authorized HTTP endpoints and ingestion."""

import asyncio

import httpx
import pytest

from agentic_rag.api.app import create_app
from agentic_rag.api.deps import get_principal
from agentic_rag.core.config import Settings
from agentic_rag.models.principal import Principal
from agentic_rag.models.upload import Upload


@pytest.fixture
async def management():
    app = create_app(Settings(environment="demo"))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client, app.state.runtime, app


async def uploaded(
    client,
    name="Reference",
    filename="reference.md",
    content=b"# Overview\n\nSynthetic Saturn reference.",
):
    kb = (await client.post("/api/v2/kb", json={"name": name})).json()
    response = await client.post(
        f"/api/v2/kb/{kb['id']}/documents", files=[("files", (filename, content, "text/plain"))]
    )
    assert response.status_code == 202
    doc = (await client.get(f"/api/v2/kb/{kb['id']}")).json()["documents"][0]
    return kb, doc


async def test_details_paginated_preview_and_exact_unicode_download(management):
    client, runtime, _ = management
    original = "# Résumé\n\nSynthetic Saturn reference with rings.\n".encode()
    kb, doc = await uploaded(client, filename='résumé "rings".md', content=original)
    detail = (await client.get(f"/api/v2/kb/{kb['id']}")).json()
    assert detail["can_delete"] and detail["documents"][0]["can_delete"]
    assert detail["documents"][0]["updated_at"]
    response = await client.get(f"/api/v2/documents/{doc['id']}/download?version=1")
    assert response.content == original
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "attachment;" in response.headers["content-disposition"]
    assert "%C3%A9" in response.headers["content-disposition"]
    offset, parts = 0, []
    while offset is not None:
        page = await client.get(
            f"/api/v2/documents/{doc['id']}/preview?limit=7&offset={offset}&version=1"
        )
        assert page.status_code == 200
        data = page.json()
        assert data["offset"] == offset
        assert sum(len(section["text"]) for section in data["sections"]) <= 7
        parts.extend(section["text"] for section in data["sections"])
        offset = data["next_offset"]
    expected = "".join(
        text for text, _, _ in runtime.knowledge.parser.parse(Upload(doc["title"], original))
    )
    assert "".join(parts) == expected
    assert (
        await client.get(f"/api/v2/documents/{doc['id']}/preview?limit=50001")
    ).status_code == 422
    assert (
        await client.get(f"/api/v2/documents/{doc['id']}/download?version=2")
    ).status_code == 409
    assert (await client.get(f"/api/v2/documents/{doc['id']}/preview?version=2")).status_code == 409


async def test_delete_document_then_base_keeps_chats_and_detaches_every_reader(management):
    client, runtime, app = management
    kb, doc = await uploaded(client)
    own = (await client.post("/api/v2/sessions", json={"kb_ids": [kb["id"]]})).json()
    other = Principal("other-user", "demo-tenant")
    other_session = await runtime.sessions.create(other, kb_ids=[kb["id"]])
    assert (await client.delete(f"/api/v2/documents/{doc['id']}")).status_code == 204
    assert (await client.get(f"/api/v2/kb/{kb['id']}")).json()["documents"] == []
    for suffix in ("preview", "download"):
        assert (await client.get(f"/api/v2/documents/{doc['id']}/{suffix}")).status_code == 403
    assert (await client.delete(f"/api/v2/kb/{kb['id']}")).status_code == 204
    assert (await client.get("/api/v2/kb")).json() == []
    assert (await client.get(f"/api/v2/sessions/{own['id']}")).json()["kb_ids"] == []
    assert (await client.get("/api/v2/sessions")).json()[0]["kb_ids"] == []
    app.dependency_overrides[get_principal] = lambda: other
    assert (await client.get(f"/api/v2/sessions/{other_session['id']}")).json()["kb_ids"] == []
    assert (
        await client.patch(
            f"/api/v2/sessions/{other_session['id']}", json={"title": "Still usable"}
        )
    ).status_code == 200
    assert (await runtime.repo.get_session(other_session["id"], other))["kb_ids"] == []


async def test_capabilities_and_originals_obey_owner_group_and_tenant_access(management):
    client, runtime, app = management
    owner = Principal("owner", "demo-tenant")
    app.dependency_overrides[get_principal] = lambda: owner
    kb, doc = await uploaded(client)
    detail = (await client.get(f"/api/v2/kb/{kb['id']}")).json()
    assert not detail["can_delete"] and detail["documents"][0]["can_delete"]
    assert (await client.delete(f"/api/v2/kb/{kb['id']}")).status_code == 403
    reader = Principal("reader", "demo-tenant")
    app.dependency_overrides[get_principal] = lambda: reader
    assert (await client.get(f"/api/v2/kb/{kb['id']}")).json()["documents"][0][
        "can_delete"
    ] is False
    assert (await client.get(f"/api/v2/documents/{doc['id']}/download")).status_code == 200
    assert (await client.delete(f"/api/v2/documents/{doc['id']}")).status_code == 403
    runtime.store.docs[doc["id"]].groups = frozenset({"restricted"})
    for suffix in ("download", "preview"):
        assert (await client.get(f"/api/v2/documents/{doc['id']}/{suffix}")).status_code == 403
    app.dependency_overrides[get_principal] = lambda: Principal("reader", "different-tenant")
    assert (await client.get("/api/v2/kb")).json() == []
    assert (await client.get(f"/api/v2/kb/{kb['id']}")).status_code == 403
    for suffix in ("download", "preview"):
        assert (await client.get(f"/api/v2/documents/{doc['id']}/{suffix}")).status_code == 403


async def test_missing_original_and_failed_index_leave_metadata_manageable(management, monkeypatch):
    client, runtime, _ = management

    async def failed(_):
        raise RuntimeError("synthetic embedding failure")

    monkeypatch.setattr(runtime.worker.embed, "documents", failed)
    kb, doc = await uploaded(client)
    assert doc["status"] == "failed"
    assert (await client.get(f"/api/v2/documents/{doc['id']}/download")).status_code == 200
    assert (await client.get(f"/api/v2/documents/{doc['id']}/preview")).status_code == 200
    runtime.store.blobs.pop(doc["id"])
    for suffix in ("download", "preview"):
        response = await client.get(f"/api/v2/documents/{doc['id']}/{suffix}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "CONTENT_UNAVAILABLE"
    assert (await client.get(f"/api/v2/kb/{kb['id']}")).json()["documents"]
    assert (await client.delete(f"/api/v2/documents/{doc['id']}")).status_code == 204


async def test_invalid_batch_preserves_existing_documents(management):
    client, _, _ = management
    kb, doc = await uploaded(client)
    response = await client.post(
        f"/api/v2/kb/{kb['id']}/documents",
        files=[
            ("files", ("valid.txt", b"Valid synthetic text")),
            ("files", ("invalid.exe", b"invalid")),
        ],
    )
    assert response.status_code == 422
    assert [d["id"] for d in (await client.get(f"/api/v2/kb/{kb['id']}")).json()["documents"]] == [
        doc["id"]
    ]


@pytest.mark.parametrize("delete_base", [False, True])
@pytest.mark.parametrize("running", [False, True])
async def test_deletion_terminates_ingestion_without_republishing(
    runtime, principal, monkeypatch, delete_base, running
):
    kb = await runtime.knowledge.create_kb("Deletion race", principal)
    jobs = await runtime.knowledge.submit(
        [Upload("race.txt", b"Synthetic unique deletion marker")], kb["id"], principal
    )
    started, release = asyncio.Event(), asyncio.Event()
    original = runtime.worker.embed.documents

    async def delayed(texts):
        started.set()
        await release.wait()
        return await original(texts)

    monkeypatch.setattr(runtime.worker.embed, "documents", delayed)
    task = None
    if running:
        task = asyncio.create_task(runtime.worker.once(principal))
        await asyncio.wait_for(started.wait(), 5)
    if delete_base:
        await runtime.knowledge.delete_kb(kb["id"], principal)
    else:
        await runtime.knowledge.delete(jobs[0].document_id, principal)
    release.set()
    if task:
        await asyncio.wait_for(task, 5)
    assert (await runtime.knowledge.status(jobs[0].id, principal)).error == "SourceDeleted"
    assert not any(
        chunk.document_id == jobs[0].document_id for chunk in runtime.store.chunks.values()
    )
    with pytest.raises(PermissionError):
        await runtime.knowledge.original(jobs[0].document_id, principal)
