"""The committed contract describes actual serialized responses and execution events."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from backend.errors import ApplicationError, normalize_error
from backend.models import ErrorCode, TokenEvent, TokenFrame
from devtools import contracts
from tests.support import ScriptedLLM
from tests.test_querying import decode_sse, no_sleep
from tests.test_routes import create_kb

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = json.loads((ROOT / "contracts/openapi.json").read_text())
CASES = json.loads((ROOT / "contracts/fixtures/payloads.json").read_text())


def validator(pointer: str) -> Draft202012Validator:
    # Formats are annotations, as in the browser; structure and constraints assert.
    return Draft202012Validator({**CONTRACT, "$ref": pointer})


def response_schema(path: str, method: str, status: int) -> str:
    path = path.replace("~", "~0").replace("/", "~1")
    return f"#/paths/{path}/{method}/responses/{status}/content/application~1json/schema"


def validate_response(response, path: str, method: str = "get") -> dict | list:
    payload = response.json()
    validator(response_schema(path, method, response.status_code)).validate(payload)
    return payload


def validate_stream(response) -> list[tuple[str, dict]]:
    events = [decode_sse(frame) for frame in response.text.strip().split("\n\n")]
    for name, data in events:
        validator("#/components/schemas/ExecutionEvent").validate({"type": name, "data": data})
    assert events[-1][0] in {"complete", "error"}
    assert all(name not in {"complete", "error"} for name, _ in events[:-1])
    return events


def test_schema_is_consistent_isolated_and_resolvable(app, monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("Contract export must not acquire runtime resources")

    (tmp_path / ".env").write_text("CHUNK_SIZE=invalid\nOPENAI_API_KEY=private-sentinel\n")
    monkeypatch.setenv("CHUNK_SIZE", "invalid")
    monkeypatch.setenv("CORS_ORIGINS", "invalid-json")
    monkeypatch.setenv("OPENAI_API_KEY", "private-sentinel")
    monkeypatch.setattr("backend.main.build_services", forbidden)
    monkeypatch.setattr("backend.storage.KBStore", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    first = contracts.export_schema()
    assert first == contracts.export_schema() == app.openapi() == CONTRACT
    assert "private-sentinel" not in json.dumps(first)
    assert app.state.services is None

    def walk(value):
        if isinstance(value, dict):
            if "$ref" in value:
                pointer = value["$ref"]
                assert pointer.startswith("#/")
                resolved = first
                for part in pointer[2:].split("/"):
                    resolved = resolved[part.replace("~1", "/").replace("~0", "~")]
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(first)
    for definition in first["components"]["schemas"].values():
        Draft202012Validator.check_schema(definition)
    for path in ("/api/chat/stream", "/api/kb/{kb_id}/query/stream"):
        operation = first["paths"][path]["post"]
        assert operation["x-event-schema"] == {"$ref": "#/components/schemas/ExecutionEvent"}
        assert set(operation["responses"]["200"]["content"]) == {"text/event-stream"}


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_shared_payload_fixtures(case):
    assert validator(case["schema"]).is_valid(case["payload"]) is case["valid"]


@pytest.mark.parametrize("code", list(ErrorCode))
def test_serialized_error_catalog(code):
    payload = normalize_error(ApplicationError(code)).payload()
    validator("#/components/schemas/ErrorEnvelope").validate(payload)
    assert "details" not in payload["error"]


async def test_all_json_routes_and_streams_serialize_to_the_contract(app_client, monkeypatch):
    import backend.querying.stream as streams

    monkeypatch.setattr(streams.asyncio, "sleep", no_sleep)
    for path in ("/", "/api/health", "/api/models/config", "/api/kb"):
        validate_response(await app_client.get(path), path)

    created = await create_kb(app_client)
    validator(response_schema("/api/kb", "post", 200)).validate(created)
    detail = validate_response(await app_client.get(f"/api/kb/{created['id']}"), "/api/kb/{kb_id}")
    assert detail == created
    validate_response(await app_client.get("/api/kb"), "/api/kb")
    validate_response(await app_client.get("/api/kb/missing"), "/api/kb/{kb_id}")
    validate_response(await app_client.post("/api/chat", json={}), "/api/chat", "post")
    validate_response(
        await app_client.post("/api/chat", json={"messages": []}), "/api/chat", "post"
    )

    query_url = f"/api/kb/{created['id']}/query"
    query = validate_response(
        await app_client.post(query_url, json={"question": "offline"}),
        "/api/kb/{kb_id}/query",
        "post",
    )
    events = validate_stream(
        await app_client.post(query_url + "/stream", json={"question": "offline"})
    )
    assert query["sources"] == next(data["sources"] for name, data in events if name == "sources")
    assert {name for name, _ in events} == {"step", "sources", "token", "complete"}

    monkeypatch.setattr(
        "backend.llm.get_llm",
        lambda settings: ScriptedLLM(invoke=["answer"], stream=["an", "swer"]),
    )
    messages = {"messages": [{"role": "user", "content": "question"}]}
    validate_response(await app_client.post("/api/chat", json=messages), "/api/chat", "post")
    events = validate_stream(await app_client.post("/api/chat/stream", json=messages))
    assert events[-1] == ("complete", {"answer": "answer"})

    monkeypatch.setattr(
        "backend.llm.get_llm",
        lambda settings: ScriptedLLM(stream=["partial", RuntimeError("private-sentinel")]),
    )
    response = await app_client.post("/api/chat/stream", json=messages)
    assert validate_stream(response)[-1][0] == "error"
    assert "private-sentinel" not in response.text


async def test_invalid_internal_event_becomes_safe_terminal_error(app_client, monkeypatch):
    import backend.querying.stream as streams

    async def invalid_events(*args):
        event = TokenFrame.model_construct(data=TokenEvent.model_construct(token=123))
        yield streams._sse(event)

    monkeypatch.setattr(streams, "_chat", invalid_events)
    response = await app_client.post("/api/chat/stream", json={"messages": []})
    events = validate_stream(response)
    assert len(events) == 1
    assert events[0][1]["error"]["code"] == "INTERNAL_ERROR"
    assert "event: token" not in response.text


@pytest.mark.parametrize("change", ["missing", "edited", "extra"])
def test_drift_check_is_read_only(tmp_path, monkeypatch, capsys, change):
    committed, regenerated = tmp_path / "committed", tmp_path / "regenerated"
    for root in (committed, regenerated):
        for name in contracts.ARTIFACTS:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("canonical\n")
    assert contracts.compare(committed, regenerated)
    target = committed / contracts.ARTIFACTS[-1]
    if change == "missing":
        target.unlink()
    elif change == "edited":
        target.write_text("manual change\n")
    else:
        (target.parent / "unexpected.d.ts").write_text("extra\n")
    before = {str(p): p.read_bytes() for p in committed.rglob("*") if p.is_file()}
    assert not contracts.compare(committed, regenerated)

    def generate_snapshot(destination):
        for name in contracts.ARTIFACTS:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((regenerated / name).read_bytes())

    monkeypatch.setattr(contracts, "ROOT", committed)
    monkeypatch.setattr(contracts, "generate", generate_snapshot)
    monkeypatch.setattr(sys, "argv", ["contracts", "check"])
    assert contracts.main() == 1
    assert "uv run --no-sync python -m devtools.contracts generate" in capsys.readouterr().out
    assert before == {str(p): p.read_bytes() for p in committed.rglob("*") if p.is_file()}
