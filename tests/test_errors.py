"""Offline public-error semantics, privacy, correlation and terminal outcomes."""

from __future__ import annotations

import asyncio
import json
import queue
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from langchain_core.documents import Document
from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    PermissionDeniedError,
    RateLimitError,
)
from starlette.exceptions import HTTPException
from starlette.requests import ClientDisconnect

import backend.llm as providers
import backend.querying.stream as streams
from backend.errors import (
    CATALOG,
    ApplicationError,
    correlation_context,
    normalize_error,
    report_failure,
    validation_issue,
)
from backend.models import ChatResponse, ChatStreamRequest, ErrorCode
from tests.support import ScriptedLLM
from tests.test_querying import collect_events, manifest, no_sleep
from tests.test_routes import create_kb

PRIVATE = "private-diagnostic-sentinel"
MESSAGES = {"messages": [{"role": "user", "content": PRIVATE}]}


def provider_failure(kind: str) -> Exception:
    request = httpx.Request(
        "POST", f"https://{PRIVATE}.example/v1", headers={"Authorization": PRIVATE}
    )
    if kind == "connection":
        return APIConnectionError(message=PRIVATE, request=request)
    if kind == "timeout":
        return APITimeoutError(request)
    if kind == "unknown":
        return APIError(PRIVATE, request, body={"secret": PRIVATE})
    if kind == "unexpected":
        return ValueError(PRIVATE)
    status, cls = {
        "rate": (429, RateLimitError),
        "quota": (429, RateLimitError),
        "auth": (401, AuthenticationError),
        "access": (403, PermissionDeniedError),
        "request": (400, BadRequestError),
        "server": (500, InternalServerError),
        "other_status": (302, APIStatusError),
    }[kind]
    body = {"code": "insufficient_quota" if kind == "quota" else PRIVATE, "message": PRIVATE}
    return cls(PRIVATE, response=httpx.Response(status, request=request), body=body)


def assert_http(response, code, status):
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert error["correlation_id"] == response.headers["X-Correlation-ID"]
    UUID(error["correlation_id"])
    assert PRIVATE not in response.text
    return error


CASES = [
    ("rate", ErrorCode.RATE_LIMITED),
    ("quota", ErrorCode.QUOTA_EXCEEDED),
    ("auth", ErrorCode.PROVIDER_AUTH_ERROR),
    ("access", ErrorCode.PROVIDER_AUTH_ERROR),
    ("request", ErrorCode.PROVIDER_REQUEST_ERROR),
    ("server", ErrorCode.PROVIDER_UNAVAILABLE),
    ("connection", ErrorCode.PROVIDER_UNAVAILABLE),
    ("timeout", ErrorCode.PROVIDER_TIMEOUT),
    ("unknown", ErrorCode.PROVIDER_ERROR),
    ("other_status", ErrorCode.PROVIDER_ERROR),
    ("unexpected", ErrorCode.INTERNAL_ERROR),
]


@pytest.mark.parametrize(("kind", "code"), CASES)
async def test_provider_failures_match_across_all_transports(
    app_client, monkeypatch, caplog, kind, code
):
    kb = await create_kb(app_client)

    def fail(settings):
        raise provider_failure(kind)

    monkeypatch.setattr(providers, "get_llm", fail)
    payloads = []
    for path, body in [
        ("/api/chat", MESSAGES),
        (f"/api/kb/{kb['id']}/query", {"question": PRIVATE}),
    ]:
        response = await app_client.post(path, json=body)
        error = assert_http(response, code, CATALOG[code].status)
        payloads.append({k: v for k, v in error.items() if k != "correlation_id"})
        streamed = await app_client.post(path + "/stream", json=body)
        assert streamed.status_code == 200
        assert streamed.text.count("event: error\n") == 1
        assert "event: complete" not in streamed.text
        frame = streamed.text.split("data: ", 1)[1].strip()
        stream_error = json.loads(frame)["error"]
        assert stream_error["correlation_id"] == streamed.headers["X-Correlation-ID"]
        payloads.append({k: v for k, v in stream_error.items() if k != "correlation_id"})
        assert PRIVATE not in streamed.text
    assert payloads == [payloads[0]] * 4
    assert payloads[0]["retryable"] is CATALOG[code].retryable
    records = [
        json.loads(record.message) for record in caplog.records if record.name == "backend.errors"
    ]
    assert len(records) == 4
    assert all(record["stack"] and record["exceptions"] for record in records)
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize(
    "body,field,issue",
    [
        ({"model_config_override": {"api_key": PRIVATE}}, "messages", "required"),
        (
            {"messages": [{"role": "user", "content": {"secret": PRIVATE}}]},
            "messages[0].content",
            "invalid_type",
        ),
        (
            {"messages": [], "model_config_override": {"api_key": [PRIVATE]}},
            "model_config_override.api_key",
            "invalid_type",
        ),
    ],
)
async def test_validation_uses_only_declared_paths(app_client, caplog, body, field, issue):
    response = await app_client.post("/api/chat", json=body)
    error = assert_http(response, ErrorCode.VALIDATION_ERROR, 422)
    assert error["details"] == [validation_issue(field, issue).model_dump()]
    assert PRIVATE not in caplog.text


async def test_validation_limit_json_and_multipart_errors(app_client):
    response = await app_client.post("/api/chat", json={"messages": [{}] * 30})
    assert len(assert_http(response, ErrorCode.VALIDATION_ERROR, 422)["details"]) == 20
    malformed = await app_client.post(
        "/api/chat", content='{"secret":"' + PRIVATE, headers={"Content-Type": "application/json"}
    )
    assert assert_http(malformed, ErrorCode.VALIDATION_ERROR, 422)["details"] == [
        validation_issue("request", "invalid_json").model_dump()
    ]
    multipart = await app_client.post(
        "/api/kb", content=PRIVATE, headers={"Content-Type": "multipart/form-data"}
    )
    assert_http(multipart, ErrorCode.BAD_REQUEST, 400)
    missing_files = await app_client.post(
        "/api/kb", data={"name": PRIVATE, "embedding_model": "offline"}
    )
    assert (
        assert_http(missing_files, ErrorCode.VALIDATION_ERROR, 422)["details"][0]["field"]
        == "files"
    )


def test_validation_never_echoes_unrecognized_keys():
    route = SimpleNamespace(
        body_field=SimpleNamespace(field_info=SimpleNamespace(annotation=ChatStreamRequest))
    )
    request = Request({"type": "http", "route": route})
    exc = RequestValidationError(
        [{"type": "value_error", "loc": ("body", PRIVATE), "msg": PRIVATE, "input": PRIVATE}]
    )
    payload = normalize_error(exc, request=request).payload()
    assert payload["error"]["details"] == [validation_issue("request").model_dump()]
    assert PRIVATE not in json.dumps(payload)


async def test_routing_conflict_unknown_http_and_response_validation(
    app: FastAPI, app_client, caplog
):
    @app.get("/fault/conflict")
    async def conflict():
        raise ApplicationError(ErrorCode.CONFLICT)

    @app.get("/fault/http")
    async def other_http():
        raise HTTPException(418, detail=PRIVATE, headers={"X-Private": PRIVATE})

    @app.get("/fault/response", response_model=ChatResponse)
    async def invalid_response():
        return {"answer": {"secret": PRIVATE}}

    assert_http(await app_client.get("/api/missing"), ErrorCode.NOT_FOUND, 404)
    method = await app_client.put("/api/health")
    assert_http(method, ErrorCode.METHOD_NOT_ALLOWED, 405)
    assert "GET" in method.headers["Allow"]
    assert_http(await app_client.get("/fault/conflict"), ErrorCode.CONFLICT, 409)
    unknown = await app_client.get("/fault/http")
    assert_http(unknown, ErrorCode.HTTP_ERROR, 418)
    assert "X-Private" not in unknown.headers
    assert_http(await app_client.get("/fault/response"), ErrorCode.INTERNAL_ERROR, 500)
    assert PRIVATE not in caplog.text


async def test_correlation_is_server_owned_and_isolated(app, app_client, caplog):
    gate = asyncio.Event()
    arrived = 0

    @app.get("/fault/concurrent")
    async def concurrent(request: Request):
        nonlocal arrived
        before = correlation_context.get()
        assert before == request.state.correlation_id
        arrived += 1
        if arrived == 2:
            gate.set()
        await gate.wait()
        assert correlation_context.get() == before
        raise RuntimeError(PRIVATE)

    responses = await asyncio.gather(
        *[
            app_client.get(
                "/fault/concurrent",
                headers={"X-Correlation-ID": PRIVATE, "Origin": "http://localhost:3000"},
            )
            for _ in range(2)
        ]
    )
    ids = [
        assert_http(response, ErrorCode.INTERNAL_ERROR, 500)["correlation_id"]
        for response in responses
    ]
    assert len(set(ids)) == 2
    for response in responses:
        assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert "X-Correlation-ID" in response.headers["access-control-expose-headers"]
    records = [
        json.loads(record.message) for record in caplog.records if record.name == "backend.errors"
    ]
    assert {record["correlation_id"] for record in records} == set(ids)
    assert correlation_context.get() is None
    assert PRIVATE not in caplog.text
    success = await app_client.get("/api/health")
    UUID(success.headers["X-Correlation-ID"])


@pytest.mark.parametrize("streamed", [False, True])
async def test_generation_failure_never_becomes_answer(app_client, monkeypatch, streamed):
    kb = await create_kb(app_client)
    monkeypatch.setattr(
        providers,
        "get_llm",
        lambda settings: ScriptedLLM(
            invoke=["rewritten", "yes", provider_failure("quota")],
            stream=["partial", provider_failure("quota")],
        ),
    )
    response = await app_client.post(
        f"/api/kb/{kb['id']}/query" + ("/stream" if streamed else ""), json={"question": PRIVATE}
    )
    if streamed:
        assert "partial" in response.text
        assert "event: complete" not in response.text
        assert response.text.count("event: error") == 1
        assert '"code": "QUOTA_EXCEEDED"' in response.text
    else:
        assert_http(response, ErrorCode.QUOTA_EXCEEDED, 429)
    assert "Error generating answer" not in response.text
    assert PRIVATE not in response.text


@pytest.mark.parametrize("stage", ["retrieve", "sources"])
async def test_query_stage_failures_are_terminal(monkeypatch, settings, stage):
    monkeypatch.setattr(streams.asyncio, "sleep", no_sleep)

    class BrokenStore:
        def search(self, query, k):
            if stage == "retrieve":
                raise RuntimeError(PRIVATE)
            return [Document(page_content="evidence", metadata={"source": None})]

    events = await collect_events(
        streams.stream_query("question", (manifest(), BrokenStore()), settings)
    )
    assert events[-1][0] == "error"
    assert not any(name == "complete" for name, _ in events)
    assert PRIVATE not in json.dumps(events)


@pytest.mark.parametrize("kind,timeout", [("chat", 30.0), ("query", 60.0)])
async def test_queue_expiry_after_partial_output_is_terminal(monkeypatch, settings, kind, timeout):
    monkeypatch.setattr(providers, "get_llm", lambda settings: ScriptedLLM(invoke=["query", "yes"]))
    monkeypatch.setattr(streams.asyncio, "sleep", no_sleep)
    calls = []

    class ExpiringQueue:
        def put(self, item):
            pass

        def get(self, *, timeout):
            calls.append(timeout)
            if len(calls) == 1:
                return "token", "partial"
            raise queue.Empty

    monkeypatch.setattr(streams.queue, "Queue", ExpiringQueue)
    store = type(
        "Store", (), {"search": lambda self, query, k: [Document(page_content="context")]}
    )()
    iterator = (
        streams.stream_chat("hello", settings)
        if kind == "chat"
        else streams.stream_query("question", (manifest(), store), settings)
    )
    events = await collect_events(iterator)
    assert calls == [timeout, timeout]
    assert ("token", {"token": "partial"}) in events
    assert events[-1][1]["error"]["code"] == "PROVIDER_TIMEOUT"
    assert sum(name == "error" for name, _ in events) == 1
    assert not any(name == "complete" for name, _ in events)


@pytest.mark.parametrize("failure", [asyncio.CancelledError, ClientDisconnect])
async def test_stream_does_not_convert_cancellation_or_disconnect(
    monkeypatch, settings, failure, caplog
):
    def interrupted(settings):
        raise failure()

    monkeypatch.setattr(providers, "get_llm", interrupted)
    with pytest.raises(failure):
        await collect_events(streams.stream_chat("hello", settings))
    assert not caplog.records
    assert correlation_context.get() is None


def test_scrubbed_chained_diagnostics_keep_categories_not_text(caplog):
    try:
        try:
            raise provider_failure("auth")
        except Exception as exc:
            raise RuntimeError(PRIVATE) from exc
    except RuntimeError as exc:
        report_failure(exc)
    record = json.loads(caplog.records[-1].message)
    assert record["exceptions"] == ["RuntimeError", "AuthenticationError"]
    assert record["provider_status"] == 401
    assert record["stack"]
    assert PRIVATE not in caplog.text
    assert all(set(frame) == {"module", "function", "line"} for frame in record["stack"])


async def test_openapi_documents_error_contract_and_catalog(app_client):
    schema = (await app_client.get("/openapi.json")).json()
    responses = schema["paths"]["/api/chat"]["post"]["responses"]
    for status in ["400", "404", "405", "409", "422", "429", "500", "502", "503", "504"]:
        assert responses[status]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/ErrorEnvelope"
        )
    assert "QUOTA_EXCEEDED" in responses["429"]["description"]
    assert "X-Correlation-ID" in responses["500"]["headers"]
    stream = schema["paths"]["/api/chat/stream"]["post"]["responses"]["200"]
    assert set(stream["content"]) == {"text/event-stream"}
    assert "ErrorEnvelope" in stream["description"]


async def test_optional_fallback_diagnostics_are_scrubbed_and_correlated(
    app_client, monkeypatch, caplog
):
    kb = await create_kb(app_client)
    monkeypatch.setattr(
        providers,
        "get_llm",
        lambda settings: ScriptedLLM(
            invoke=[provider_failure("rate"), provider_failure("rate"), "final answer"],
        ),
    )
    response = await app_client.post(f"/api/kb/{kb['id']}/query", json={"question": PRIVATE})
    assert response.status_code == 200
    assert response.json()["answer"] == "final answer"
    records = [
        json.loads(record.message) for record in caplog.records if record.name == "backend.errors"
    ]
    assert [record["operation"] for record in records] == ["query.rewrite", "query.grade"]
    assert all(record["event"] == "optional_fallback" for record in records)
    assert all(
        record["correlation_id"] == response.headers["X-Correlation-ID"] for record in records
    )
    assert PRIVATE not in caplog.text


@pytest.mark.parametrize("kind", ["chat", "query"])
async def test_worker_exceptions_retain_provider_type_after_partial_output(
    app_client, monkeypatch, kind
):
    kb = await create_kb(app_client)
    monkeypatch.setattr(
        providers,
        "get_llm",
        lambda settings: ScriptedLLM(
            invoke=["query", "yes"],
            stream=["partial", provider_failure("timeout")],
        ),
    )
    endpoint, body = (
        ("/api/chat/stream", MESSAGES)
        if kind == "chat"
        else (f"/api/kb/{kb['id']}/query/stream", {"question": PRIVATE})
    )
    response = await app_client.post(endpoint, json=body)
    events = [
        json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")
    ]
    assert {"token": "partial"} in events
    assert events[-1]["error"]["code"] == "PROVIDER_TIMEOUT"
    assert events[-1]["error"]["correlation_id"] == response.headers["X-Correlation-ID"]
    assert "event: complete" not in response.text
    assert PRIVATE not in response.text
