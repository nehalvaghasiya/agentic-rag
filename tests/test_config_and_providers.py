"""Configuration and provider-selection regressions."""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from backend.config import Settings, get_settings, reset_settings
from backend.indexing.embedder import HashEmbedder
from backend.llm import get_embedder, get_llm


def test_explicit_settings_ignore_dotenv_and_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / ".env").write_text(
        "MODE=production\nOPENAI_API_KEY=dotenv-secret\nDATA_DIR=dotenv-data\n"
    )
    monkeypatch.setenv("OPENAI_API_KEY", "environment-secret")

    data_dir = tmp_path / "explicit-data"
    settings = Settings(
        _env_file=None,  # pyright: ignore[reportCallIssue]
        mode="deterministic",
        data_dir=data_dir,
        upload_dir=data_dir / "uploads",
        openai_api_key=None,
    )

    assert settings.mode == "deterministic"
    assert settings.data_dir == data_dir
    assert settings.openai_api_key is None


def test_settings_singleton_can_be_reset(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MODE", "deterministic")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "first"))
    first = get_settings()

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "second"))
    assert get_settings() is first
    assert get_settings().data_dir == tmp_path / "first"

    reset_settings()
    second = get_settings()
    assert second is not first
    assert second.data_dir == tmp_path / "second"


def test_deterministic_mode_uses_offline_providers(settings: Settings) -> None:
    assert get_llm(settings) is None
    assert isinstance(get_embedder("text-embedding-3-small", settings), HashEmbedder)


def test_openai_embedder_requires_a_key_before_construction(
    settings_factory,
) -> None:
    settings = settings_factory(mode="production", openai_api_key=None)

    with pytest.raises(ValueError, match="OpenAI API key required"):
        get_embedder("text-embedding-3-small", settings)


def test_hash_embedder_is_stable_and_respects_dimensions() -> None:
    embedder = HashEmbedder(dims=17)

    first = embedder.embed_query("repeatable")
    second = embedder.embed_documents(["repeatable"])[0]

    assert first == second
    assert len(first) == 17
    assert all(0.0 <= value <= 1.0 for value in first)


def test_network_fixture_rejects_even_loopback_connections() -> None:
    with pytest.raises(AssertionError, match="Network access is forbidden"):
        socket.create_connection(("127.0.0.1", 9))
