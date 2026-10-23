"""Public JSON requests are bounded before storage, providers, or streams start."""

from __future__ import annotations

import asyncio
import json
import re
from unittest.mock import Mock

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from backend.models import ChatMessage, ChatRequest, ChatStreamRequest, ModelConfig, QueryRequest
from backend.request_limits import (
    MAX_API_KEY_CHARACTERS,
    MAX_BASE_URL_CHARACTERS,
    MAX_HISTORY_CHARACTERS,
    MAX_HISTORY_MESSAGES,
    MAX_JSON_BODY_BYTES,
    MAX_MODEL_CHARACTERS,
    MAX_TEXT_CHARACTERS,
    NONBLANK_PATTERN,
)

ENDPOINTS = (
    "/api/chat",
    "/api/chat/stream",
    "/api/kb/missing/query",
    "/api/kb/missing/query/stream",
)
SENTINEL = "private-request-sentinel"
WHITESPACE = ("", " ", "\t\r\n", "\u00a0", "\u0085", "\u2003", "\u001c\u2028\u3000")


def conversation(*contents: str, final_role: str = "user") -> dict:
    return {
        "messages": [{"role": "user", "content": text} for text in contents[:-1]]
        + [{"role": final_role, "content": contents[-1]}]
    }


def valid_payload(endpoint: str) -> dict:
    return conversation("question") if "/chat" in endpoint else {"question": "question"}


@pytest.fixture
def no_request_work(monkeypatch):
    """Patch request-specific entry points after lifespan-owned services exist."""
    mock = Mock(side_effect=AssertionError("Invalid input started request work"))
    for name in (
        "backend.llm.get_llm",
        "backend.llm.get_embedder",
        "backend.storage.KBStore.load",
        "backend.storage.VectorStore.search",
        "backend.routes._apply_model_override",
        "backend.routes.stream_chat",
        "backend.routes.stream_query",
        "backend.querying.nodes.rewrite_query",
        "backend.querying.nodes.retrieve",
        "backend.querying.nodes.grade",
        "backend.querying.nodes.generate",
        "backend.querying.nodes.generate_stream",
    ):
        monkeypatch.setattr(name, mock)
    return mock


def assert_rejected(response, status: int = 422):
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/json")
    error = response.json()["error"]
    assert error["code"] == ("VALIDATION_ERROR" if status == 422 else "PAYLOAD_TOO_LARGE")
    assert error["retryable"] is False
    assert error["correlation_id"] == response.headers["X-Correlation-ID"]
    assert "event:" not in response.text
    assert SENTINEL not in response.text
    if status == 413:
        assert error["message"] == "The request is too large. Reduce its size and try again."
        assert "details" not in error
    return error


@pytest.mark.parametrize("text", WHITESPACE)
def test_nonblank_text_is_preserved_and_unicode_aware(text):
    for model, field in ((QueryRequest, "question"), (ChatMessage, "content")):
        with pytest.raises(ValidationError):
            model.model_validate({field: text, **({"role": "user"} if field == "content" else {})})
    original = "\n    print('👋')\n  "
    assert QueryRequest(question=original).question == original
    assert ChatMessage(role="user", content=original).content == original


def test_pattern_matches_python_unicode_whitespace_definition():
    # Every Unicode code point is checked, including control whitespace missing from JS \s.
    for codepoint in range(0x110000):
        character = chr(codepoint)
        assert bool(re.search(NONBLANK_PATTERN, character)) is (not character.isspace())


@pytest.mark.parametrize("character", ["a", "👋"])
def test_text_length_counts_code_points_and_original_padding(character):
    text = character * MAX_TEXT_CHARACTERS
    assert QueryRequest(question=text).question == text
    assert ChatMessage(role="user", content=text).content == text
    for value in (text + character, " " + text):
        with pytest.raises(ValidationError):
            QueryRequest(question=value)
        with pytest.raises(ValidationError):
            ChatMessage(role="user", content=value)


def test_chat_count_aggregate_and_final_role_boundaries():
    assert ChatStreamRequest is ChatRequest
    assert (
        len(ChatRequest.model_validate(conversation(*(["x"] * MAX_HISTORY_MESSAGES))).messages)
        == 50
    )
    assert (
        sum(
            len(m.content)
            for m in ChatRequest.model_validate(
                conversation(*(["x" * MAX_TEXT_CHARACTERS] * 8))
            ).messages
        )
        == MAX_HISTORY_CHARACTERS
    )
    for payload in (
        {"messages": []},
        conversation(*(["x"] * 51)),
        conversation(*(["x" * MAX_TEXT_CHARACTERS] * 8), "x"),
        conversation("answer", final_role="assistant"),
    ):
        with pytest.raises(ValidationError):
            ChatRequest.model_validate(payload)
    history = {
        "messages": [
            {"role": "assistant", "content": "greeting"},
            {"role": "user", "content": "first"},
            {"role": "user", "content": "second"},
        ]
    }
    assert len(ChatRequest.model_validate(history).messages) == 3


@pytest.mark.parametrize(
    "field,limit",
    [
        ("api_key", MAX_API_KEY_CHARACTERS),
        ("model", MAX_MODEL_CHARACTERS),
        ("base_url", MAX_BASE_URL_CHARACTERS),
    ],
)
def test_optional_override_boundaries(field, limit):
    assert getattr(ModelConfig.model_validate({field: "x" * limit}), field) == "x" * limit
    assert getattr(ModelConfig.model_validate({field: None}), field) is None
    assert getattr(ModelConfig(), field) is None
    for value in ("x" * (limit + 1), *WHITESPACE, 1, True, [], {}):
        with pytest.raises(ValidationError):
            ModelConfig.model_validate({field: value})
    for override in (None, {}, {field: None}):
        assert QueryRequest(question="q", model_config_override=override).question == "q"


def invalid_cases(endpoint):
    base = valid_payload(endpoint)
    cases = [
        None,
        [],
        "string",
        {},
        {**base, SENTINEL: SENTINEL},
        {**base, "system_prompt": SENTINEL},
        {**base, "tools": []},
        {**base, "model_config_override": {SENTINEL: SENTINEL}},
        {**base, "model_config_override": {"system_prompt": SENTINEL}},
        {**base, "model_config_override": []},
    ]
    for field, limit in (
        ("api_key", MAX_API_KEY_CHARACTERS),
        ("model", MAX_MODEL_CHARACTERS),
        ("base_url", MAX_BASE_URL_CHARACTERS),
    ):
        for value in ("x" * (limit + 1), " ", 1, True, [], {}):
            cases.append({**base, "model_config_override": {field: value}})
    if "/chat" in endpoint:
        cases.extend(
            [
                {"messages": []},
                {"messages": "text"},
                conversation(*(["x"] * 51)),
                conversation(*(["x" * 8000] * 8), "x"),
                conversation("answer", final_role="assistant"),
            ]
        )
        for role in (
            "system",
            "developer",
            "tool",
            "arbitrary",
            "USER",
            "Assistant",
            " user ",
            1,
            None,
        ):
            cases.append(conversation(SENTINEL, final_role=role))
        for value in (*WHITESPACE, "x" * 8001, 1, True, None, [], {}):
            cases.append({"messages": [{"role": "user", "content": value}]})
        for name in (SENTINEL, "additional_kwargs", "name", "tool_calls"):
            cases.append({"messages": [{"role": "user", "content": "q", name: SENTINEL}]})
    else:
        for value in (*WHITESPACE, "x" * 8001, 1, True, None, [], {}):
            cases.append({"question": value})
    return cases


@pytest.mark.parametrize(
    "endpoint,payload",
    [(endpoint, payload) for endpoint in ENDPOINTS for payload in invalid_cases(endpoint)],
)
async def test_invalid_requests_do_no_work(app_client, no_request_work, caplog, endpoint, payload):
    response = await app_client.post(
        endpoint, content=json.dumps(payload), headers={"Content-Type": "application/json"}
    )
    assert_rejected(response)
    no_request_work.assert_not_called()
    assert SENTINEL not in caplog.text


@pytest.mark.parametrize("endpoint", ENDPOINTS)
async def test_exact_body_limit_passes_validation(app_client, monkeypatch, endpoint):
    # A valid request that reaches the first work boundary proves the cap is inclusive.
    calls = Mock(return_value=None)
    monkeypatch.setattr("backend.llm.get_llm", calls)
    monkeypatch.setattr("backend.storage.KBStore.load", calls)
    payload = json.dumps(valid_payload(endpoint)).encode()
    body = payload + b" " * (MAX_JSON_BODY_BYTES - len(payload))
    response = await app_client.post(
        endpoint, content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == (
        200 if endpoint == "/api/chat/stream" else 503 if endpoint == "/api/chat" else 404
    )
    calls.assert_called_once()


async def test_maximum_unicode_history_fits_even_when_json_escaped(app_client, monkeypatch):
    provider = Mock(return_value=None)
    monkeypatch.setattr("backend.llm.get_llm", provider)
    payload = json.dumps(conversation(*(["👋" * MAX_TEXT_CHARACTERS] * 8))).encode()
    assert len(payload) < MAX_JSON_BODY_BYTES
    response = await app_client.post(
        "/api/chat", content=payload, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 503
    provider.assert_called_once()


@pytest.mark.parametrize("endpoint", ENDPOINTS)
@pytest.mark.parametrize("length_header", [None, "1", str(MAX_JSON_BODY_BYTES + 1)])
async def test_oversized_chunked_body_stops_before_decoding(
    app_client,
    monkeypatch,
    no_request_work,
    caplog,
    endpoint,
    length_header,
):
    decoder = Mock(side_effect=AssertionError("Oversized input reached JSON decoding"))
    monkeypatch.setattr(Request, "json", decoder)
    reads = []

    async def chunks():
        reads.append(1)
        yield b" " * MAX_JSON_BODY_BYTES
        reads.append(2)
        yield b"x"
        reads.append(3)
        yield SENTINEL.encode()

    headers = {"Content-Type": "application/json"}
    if length_header is not None:
        headers["Content-Length"] = length_header
    response = await app_client.post(endpoint, content=chunks(), headers=headers)
    assert_rejected(response, 413)
    assert reads == [1, 2]
    decoder.assert_not_called()
    no_request_work.assert_not_called()
    assert SENTINEL not in caplog.text


async def test_json_cap_preserves_get_and_multipart_routes(app_client, monkeypatch):
    # This tests route selection, not AnyIO's file worker pool; keep the part in memory.
    monkeypatch.setattr(
        "starlette.formparsers.MultiPartParser.spool_max_size", 2 * MAX_JSON_BODY_BYTES
    )
    for endpoint in ("/api/health", "/api/models/config", "/api/kb"):
        response = await app_client.request(
            "GET", endpoint, content=b" " * (MAX_JSON_BODY_BYTES + 1)
        )
        assert response.status_code == 200
    create = Mock(side_effect=RuntimeError("Reached multipart handler"))
    monkeypatch.setattr("backend.storage.KBStore.create", create)
    response = await app_client.post(
        "/api/kb",
        data={"name": "KB", "embedding_model": "offline"},
        files=[("files", ("large.txt", b"x" * (MAX_JSON_BODY_BYTES + 1), "text/plain"))],
    )
    assert response.status_code == 500
    create.assert_called_once()


async def test_receive_disconnect_keeps_existing_handling(app):
    messages = [
        {"type": "http.request", "body": b'{"question":', "more_body": True},
        {"type": "http.disconnect"},
    ]
    sent = []

    async def receive():
        return messages.pop(0)

    async def send(message):
        sent.append(message)

    # FastAPI classifies interrupted request bodies as BAD_REQUEST; preserve it.
    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/kb/missing/query",
            "raw_path": b"/api/kb/missing/query",
            "query_string": b"",
            "headers": [(b"content-type", b"application/json")],
            "client": ("127.0.0.1", 1),
            "server": ("test", 80),
        },
        receive,
        send,
    )
    assert sent[0]["status"] == 400
    assert json.loads(sent[1]["body"])["error"]["code"] == "BAD_REQUEST"


async def test_receive_cancellation_propagates_without_a_response(app):
    sent = []

    async def receive():
        raise asyncio.CancelledError

    async def send(message):
        sent.append(message)

    with pytest.raises(asyncio.CancelledError):
        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "POST",
                "scheme": "http",
                "path": "/api/chat",
                "raw_path": b"/api/chat",
                "query_string": b"",
                "headers": [(b"content-type", b"application/json")],
                "client": ("127.0.0.1", 1),
                "server": ("test", 80),
            },
            receive,
            send,
        )
    assert not sent
