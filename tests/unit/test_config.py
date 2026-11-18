"""Profile fail-closed behavior with deterministic environment overrides."""

import os

import pytest

from agentic_rag.core.config import Settings
from agentic_rag.core.runtime import RuntimeFactory


@pytest.fixture(autouse=True)
def isolated_settings_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    for name in os.environ:
        if name.startswith(("AGENTIC_RAG_", "LLM_", "EMBEDDING_")) or name == "OPENAI_API_KEY":
            monkeypatch.delenv(name)


def test_production_requires_nonfake_provider_and_postgres() -> None:
    with pytest.raises(ValueError, match="real model"):
        Settings(
            environment="production",
            store="postgres",
            database_url="postgresql://fake",
            provider="fake",
            jwt_secret="a" * 48,
        ).validate_runtime()


async def test_postgres_runtime_defers_connection_until_open() -> None:
    values = Settings(
        environment="production",
        store="postgres",
        provider="openai",
        database_url="postgresql://fake",
        api_key="fake",
        jwt_secret="a" * 48,
    )
    runtime = RuntimeFactory(values)
    assert type(runtime.repo).__name__ == "PostgresRepository"
    await runtime.close()


def test_yaml_without_profile_is_demo(tmp_path) -> None:
    path = tmp_path / "profile.yaml"
    path.write_text("environment: demo\nstore: fake\nprovider: fake\n")
    assert Settings.load(path).store == "fake"


def test_dotenv_loads_llm_and_independent_embedding_settings(tmp_path) -> None:
    (tmp_path / ".env").write_text(
        "LLM_PROVIDER=openai_compatible\nLLM_MODEL=auto\n"
        "LLM_BASE_URL=http://localhost:20128/v1\nLLM_API_KEY=chat-test-key\n"
        "EMBEDDING_PROVIDER=openai_compatible\nEMBEDDING_MODEL=embed-test\n"
        "EMBEDDING_BASE_URL=http://127.0.0.1:20129/v1\n"
        "EMBEDDING_API_KEY=embedding-test-key\n"
    )
    settings = Settings.load()
    settings.validate_runtime()
    assert settings.provider == "openai_compatible"
    assert settings.model == "auto"
    assert settings.api_key == "chat-test-key"
    assert settings.base_url == "http://localhost:20128/v1"
    assert settings.embedding_provider == "openai_compatible"
    assert settings.embedding_model == "embed-test"
    assert settings.embedding_api_key == "embedding-test-key"
    assert settings.embedding_base_url == "http://127.0.0.1:20129/v1"
    assert "LLM_API_KEY" not in os.environ
    assert "chat-test-key" not in str(settings.public())
    assert "embedding-test-key" not in str(settings.public())


def test_process_environment_overrides_dotenv_and_yaml(monkeypatch, tmp_path) -> None:
    profile = tmp_path / "profile.yaml"
    profile.write_text("provider: openai\nmodel: yaml-model\n")
    (tmp_path / ".env").write_text(
        "LLM_PROVIDER=openai_compatible\nLLM_MODEL=dotenv-model\n"
        "EMBEDDING_PROVIDER=openai_compatible\n"
    )
    monkeypatch.setenv("AGENTIC_RAG_PROVIDER", "fake")
    monkeypatch.setenv("AGENTIC_RAG_EMBEDDING_PROVIDER", "fake")
    monkeypatch.setenv("LLM_MODEL", "process-model")
    settings = Settings.load(profile)
    assert settings.provider == "fake"
    assert settings.embedding_provider == "fake"
    assert settings.model == "process-model"


def test_specific_api_key_overrides_legacy_openai_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-test-key")
    assert Settings.load().api_key == "legacy-test-key"
    monkeypatch.setenv("LLM_API_KEY", "llm-test-key")
    assert Settings.load().api_key == "llm-test-key"
    monkeypatch.setenv("AGENTIC_RAG_API_KEY", "specific-test-key")
    assert Settings.load().api_key == "specific-test-key"


@pytest.mark.parametrize("separate_embedding", [False, True])
async def test_runtime_selects_embedding_connection(separate_embedding) -> None:
    values = {
        "provider": "openai_compatible",
        "model": "auto",
        "api_key": "chat-test-key",
        "base_url": "http://localhost:20128/v1",
    }
    if separate_embedding:
        values.update(
            embedding_api_key="embedding-test-key", embedding_base_url="http://127.0.0.1:20129/v1"
        )
    runtime = RuntimeFactory(Settings(**values))
    try:
        assert runtime.chat.api_key == "chat-test-key"
        assert runtime.chat.base_url == "http://localhost:20128/v1"
        assert runtime.embed.api_key == (
            "embedding-test-key" if separate_embedding else "chat-test-key"
        )
        assert runtime.embed.url == (
            "http://127.0.0.1:20129/v1/embeddings"
            if separate_embedding
            else "http://localhost:20128/v1/embeddings"
        )
    finally:
        await runtime.close()
