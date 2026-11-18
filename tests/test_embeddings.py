"""OpenAI-compatible embedding requests and knowledge-base retrieval."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from langchain_openai import OpenAIEmbeddings

from backend.config import Settings, resolve_settings
from backend.dependencies import get_app_settings
from backend.errors import ApplicationError
from backend.llm import get_embedder

MODEL = "openrouter/qwen/qwen3-embedding-8b"
BASE_URL = "http://localhost:20128/v1"


@pytest.fixture
def embedding_requests(monkeypatch):
    """Exercise the real SDK and serialization without contacting a provider."""
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content)
        assert payload["encoding_format"] == "float"
        assert isinstance(payload["input"], list)
        assert all(isinstance(text, str) for text in payload["input"])
        return httpx.Response(
            200,
            json={
                "object": "list",
                "model": payload["model"],
                "data": [
                    {"object": "embedding", "index": index, "embedding": [1.0, 0.5]}
                    for index, _ in enumerate(payload["input"])
                ],
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(
            "langchain_openai.OpenAIEmbeddings",
            lambda **kwargs: OpenAIEmbeddings(http_client=client, **kwargs),
        )
        yield requests


@pytest.mark.parametrize(
    ("provider", "model", "overrides", "expected_url", "expected_key"),
    [
        ("openai", MODEL, {}, BASE_URL, "chat-key"),
        (
            "openai",
            MODEL,
            {"embedding_base_url": "http://embeddings.test/v1", "embedding_api_key": "embed-key"},
            "http://embeddings.test/v1",
            "embed-key",
        ),
        (
            "openai",
            MODEL,
            {"embedding_base_url": "", "embedding_api_key": ""},
            BASE_URL,
            "chat-key",
        ),
        ("auto", "text-embedding-3-small", {}, BASE_URL, "chat-key"),
        (
            "openai",
            MODEL,
            {"openai_api_key": None, "embedding_api_key": "embed-only-key"},
            BASE_URL,
            "embed-only-key",
        ),
    ],
)
def test_hosted_embeddings_use_configured_endpoint_and_send_plain_text(
    settings_factory, embedding_requests, provider, model, overrides, expected_url, expected_key
):
    values = {
        "mode": "production",
        "embedding_provider": provider,
        "openai_model": "auto",
        "openai_api_key": "chat-key",
        "openai_base_url": BASE_URL,
    }
    values.update(overrides)
    embedder = get_embedder(model, settings_factory(**values))

    assert embedder.embed_documents(["Hello, this is a test embedding.", "Second document"]) == [
        [1.0, 0.5],
        [1.0, 0.5],
    ]
    assert embedder.embed_query("A question?") == [1.0, 0.5]
    assert len(embedding_requests) == 2
    for request in embedding_requests:
        assert str(request.url) == expected_url + "/embeddings"
        assert request.headers["Authorization"] == f"Bearer {expected_key}"
        assert json.loads(request.content)["model"] == model
    assert json.loads(embedding_requests[0].content)["input"] == [
        "Hello, this is a test embedding.",
        "Second document",
    ]
    assert json.loads(embedding_requests[1].content)["input"] == ["A question?"]


@pytest.mark.parametrize("key", [None, ""])
def test_compatible_embeddings_require_credentials(settings_factory, key):
    settings = settings_factory(
        mode="production", embedding_provider="openai", embedding_api_key=key, openai_api_key=key
    )
    with pytest.raises(ApplicationError, match="MODEL_NOT_CONFIGURED"):
        get_embedder(MODEL, settings)


@pytest.mark.parametrize(
    ("provider", "model"),
    [("auto", "sentence-transformers/all-MiniLM-L6-v2"), ("huggingface", "text-embedding-local")],
)
def test_local_provider_selection_still_uses_huggingface(
    settings_factory, monkeypatch, provider, model
):
    local = Mock()
    monkeypatch.setattr("backend.indexing.embedder.HFEmbedder", local)
    embedder = get_embedder(model, settings_factory(mode="production", embedding_provider=provider))
    local.assert_called_once_with(model)
    assert embedder is local.return_value


def test_embedding_settings_load_from_environment_without_exposing_key(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("EMBEDDING_MODEL", MODEL)
    monkeypatch.setenv("EMBEDDING_BASE_URL", BASE_URL)
    monkeypatch.setenv("EMBEDDING_API_KEY", "private-embedding-key")
    settings = resolve_settings()
    assert settings.embedding_provider == "openai"
    assert settings.embedding_model == MODEL
    assert settings.embedding_base_url == BASE_URL
    assert settings.embedding_api_key.get_secret_value() == "private-embedding-key"
    assert "private-embedding-key" not in repr(settings)
    assert "private-embedding-key" not in settings.model_dump_json()


def test_omnirouter_dotenv_example_loads():
    example = Path(__file__).resolve().parents[1] / ".env.example"
    settings = Settings(_env_file=example)
    assert settings.embedding_provider == "openai"
    assert settings.embedding_model == MODEL
    assert settings.openai_model == "auto"
    assert settings.embedding_base_url == settings.openai_base_url == BASE_URL
    assert settings.openai_api_key.get_secret_value() == "YOUR_NEW_API_KEY"
    assert not settings.embedding_api_key


async def test_kb_upload_and_query_use_server_embeddings_and_persist_model(
    app_client, app, settings_factory, monkeypatch, embedding_requests
):
    settings = settings_factory(
        mode="production",
        embedding_provider="openai",
        embedding_model=MODEL,
        embedding_base_url=BASE_URL,
        embedding_api_key="router-key",
    )

    async def override_settings():
        return settings

    app.dependency_overrides[get_app_settings] = override_settings
    monkeypatch.setattr("backend.llm.get_llm", lambda settings: None)

    response = await app_client.post(
        "/api/kb",
        data={"name": "OmniRouter KB"},
        files=[("files", ("notes.txt", b"The answer is forty-two.", "text/plain"))],
    )
    assert response.status_code == 200, response.text
    created = response.json()
    assert created["embedding_model"] == MODEL

    # A new default or a chat override must not change an existing KB's embeddings.
    settings.embedding_model = "another-default-model"
    response = await app_client.post(
        f"/api/kb/{created['id']}/query",
        json={
            "question": "What is the answer?",
            "model_config_override": {
                "model": "chat-only-model",
                "api_key": "chat-only-key",
                "base_url": "http://chat-only.test/v1",
            },
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["sources"][0]["file_name"] == "notes.txt"
    assert len(embedding_requests) == 2
    assert json.loads(embedding_requests[0].content)["input"] == ["The answer is forty-two."]
    assert json.loads(embedding_requests[1].content)["input"] == ["What is the answer?"]
    for request in embedding_requests:
        assert str(request.url) == BASE_URL + "/embeddings"
        assert request.headers["Authorization"] == "Bearer router-key"
        assert json.loads(request.content)["model"] == MODEL
