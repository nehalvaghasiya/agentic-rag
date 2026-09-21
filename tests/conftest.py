"""Offline, isolated fixtures for backend tests."""

from __future__ import annotations

import asyncio
import socket
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from tempfile import SpooledTemporaryFile
from typing import Any, BinaryIO, cast

import httpx
import pytest
from fastapi import UploadFile
from langchain_core.documents import Document

from backend.config import Settings, reset_settings
from backend.storage import KBStore, VectorStore
from tests.support import ScriptedEmbedder, ScriptedLLM

SENSITIVE_ENVIRONMENT = (
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_BASE_URL",
    "EMBEDDING_MODEL",
    "MODE",
    "DATA_DIR",
    "UPLOAD_DIR",
    "SERPAPI_API_KEY",
    "GOOGLE_CSE_ID",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Keep settings, environment reads, and relative files isolated per test."""

    for name in SENSITIVE_ENVIRONMENT:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    reset_settings()
    yield
    reset_settings()


@pytest.fixture(autouse=True)
def deny_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn every attempted socket connection into an immediate test failure."""

    def blocked(*args: Any, **kwargs: Any) -> None:
        del args, kwargs
        raise AssertionError("Network access is forbidden in backend tests")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture(autouse=True)
def run_thread_work_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep application offloading deterministic and avoid session-level worker state."""

    async def inline(function: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
        return function(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", inline)


@pytest.fixture
def settings_factory(tmp_path: Path) -> Callable[..., Settings]:
    """Create deterministic settings whose state lives below ``tmp_path``."""

    counter = 0

    def create(**overrides: Any) -> Settings:
        nonlocal counter
        counter += 1
        data_dir = tmp_path / f"data-{counter}"
        values: dict[str, Any] = {
            "mode": "deterministic",
            "data_dir": data_dir,
            "upload_dir": data_dir / "uploads",
            "openai_api_key": None,
            "openai_base_url": None,
        }
        values.update(overrides)
        return Settings(_env_file=None, **values)  # pyright: ignore[reportCallIssue]

    return create


@pytest.fixture
def settings(settings_factory: Callable[..., Settings]) -> Settings:
    return settings_factory()


@pytest.fixture
def kb_store(settings: Settings) -> KBStore:
    return KBStore(settings.data_dir)


@pytest.fixture
def upload_file_factory() -> Callable[[str | None, bytes], UploadFile]:
    def create(filename: str | None, content: bytes) -> UploadFile:
        file = SpooledTemporaryFile(max_size=max(1, len(content) + 1))
        file.write(content)
        file.seek(0)
        return UploadFile(file=cast(BinaryIO, file), filename=filename)

    return create


@pytest.fixture
def document_factory() -> Callable[[str, dict[str, Any] | None], Document]:
    def create(text: str, metadata: dict[str, Any] | None = None) -> Document:
        return Document(page_content=text, metadata=metadata or {})

    return create


@pytest.fixture
def scripted_llm_factory() -> Callable[..., ScriptedLLM]:
    return ScriptedLLM


@pytest.fixture
def scripted_embedder_factory() -> Callable[[dict[str, list[float]]], ScriptedEmbedder]:
    return ScriptedEmbedder


@pytest.fixture
def vector_store() -> VectorStore:
    embedder = ScriptedEmbedder(
        {
            "alpha": [1.0, 0.0],
            "beta": [0.0, 1.0],
            "alpha query": [1.0, 0.0],
        }
    )
    return VectorStore(embedder)


@pytest.fixture
async def app_client(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    kb_store: KBStore,
    deny_network: None,
) -> AsyncIterator[httpx.AsyncClient]:
    """Expose the global app with route state replaced by per-test services."""

    del deny_network
    import backend.config as config

    monkeypatch.setattr(config, "_settings", settings)

    # These imports must remain inside the fixture: both modules construct state
    # during import, after the temporary working directory and settings are active.
    import backend.main as main
    import backend.routes as routes

    monkeypatch.setattr(main, "settings", settings)
    monkeypatch.setattr(routes, "_settings", settings)
    monkeypatch.setattr(routes, "_kb_store", kb_store)

    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
