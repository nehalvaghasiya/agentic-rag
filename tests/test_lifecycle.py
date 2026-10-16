"""Application ownership, startup failures, and shutdown regressions."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from contextlib import AsyncExitStack, nullcontext
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

import backend.llm as providers
from backend.config import Settings
from backend.dependencies import get_app_settings, get_kb_store
from backend.main import create_app
from backend.services import AppServices, build_services
from backend.storage import KBStore
from tests.test_routes import create_kb


def test_backend_imports_do_not_construct_configuration_or_resources(tmp_path: Path) -> None:
    script = """
import importlib
import pkgutil
import socket

import backend
import backend.config as config
import backend.llm as providers
import backend.storage as storage
from fastapi import FastAPI

def forbidden(*args, **kwargs):
    raise AssertionError("Backend imports must not construct applications or resources")

config.Settings.__init__ = forbidden
storage.KBStore.__init__ = forbidden
providers.get_llm = forbidden
providers.get_embedder = forbidden
FastAPI.__init__ = forbidden
socket.create_connection = forbidden
socket.socket.connect = forbidden
socket.socket.connect_ex = forbidden

for module in pkgutil.walk_packages(backend.__path__, prefix="backend."):
    importlib.import_module(module.name)
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={
            **os.environ,
            "MODE": "invalid-runtime-mode",
            "DATA_DIR": str(tmp_path / "unopened-data"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (tmp_path / "unopened-data").exists()
    assert not (tmp_path / ".data").exists()


async def test_factory_configures_middleware_without_starting_services(settings: Settings) -> None:
    app = create_app(settings)
    assert app.state.services is None
    assert not settings.data_dir.exists()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.options(
            "/api/kb",
            headers={
                "Origin": settings.cors_origins[0],
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == settings.cors_origins[0]
    assert app.state.services is None
    assert not settings.data_dir.exists()


async def test_factory_loads_fresh_environment_settings(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MODE", "deterministic")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "first"))
    monkeypatch.setenv("OPENAI_MODEL", "first-model")
    first = create_app()

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "second"))
    monkeypatch.setenv("OPENAI_MODEL", "second-model")
    second = create_app()

    async with first.router.lifespan_context(first), second.router.lifespan_context(second):
        assert first.state.services.settings.data_dir == tmp_path / "first"
        assert first.state.services.settings.openai_model == "first-model"
        assert second.state.services.settings.data_dir == tmp_path / "second"
        assert second.state.services.settings.openai_model == "second-model"


async def test_settings_snapshot_is_independent_of_callers_and_other_apps(
    settings: Settings,
) -> None:
    original_model = settings.openai_model
    original_origins = settings.cors_origins.copy()
    first = create_app(settings)
    second = create_app(settings)

    settings.openai_model = "changed-by-caller"
    settings.cors_origins.append("https://caller.example")
    settings.data_dir = settings.data_dir / "changed-by-caller"

    async with first.router.lifespan_context(first), second.router.lifespan_context(second):
        first_settings = first.state.services.settings
        second_settings = second.state.services.settings
        assert first_settings is not second_settings
        assert first_settings is not settings
        assert first_settings.openai_model == second_settings.openai_model == original_model
        assert first_settings.cors_origins == second_settings.cors_origins == original_origins
        assert first_settings.data_dir != settings.data_dir

        first_settings.openai_model = "changed-in-first-app"
        first_settings.cors_origins.append("https://first.example")
        assert second_settings.openai_model == original_model
        assert second_settings.cors_origins == original_origins


async def test_services_are_reused_per_lifespan_and_rebuilt_after_shutdown(
    settings: Settings,
) -> None:
    created: list[AppServices] = []
    closed: list[AppServices] = []

    async def factory(config: Settings, stack: AsyncExitStack) -> AppServices:
        services = await build_services(config, stack)
        created.append(services)
        stack.callback(closed.append, services)
        return services

    app = create_app(settings, services_factory=factory)
    for cycle in range(2):
        async with app.router.lifespan_context(app):
            assert len(created) == cycle + 1
            assert app.state.services is created[-1]
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                for endpoint in ("/api/health", "/api/kb", "/api/models/config"):
                    assert (await client.get(endpoint)).status_code == 200
                    assert app.state.services is created[-1]
            assert len(created) == cycle + 1
        assert app.state.services is None
        assert len(closed) == cycle + 1
        assert closed[-1] is created[-1]

    assert created[0] is not created[1]
    assert created[0].kb_store is not created[1].kb_store


async def test_storage_startup_failure_is_propagated(settings: Settings) -> None:
    settings.data_dir.write_text("existing file")
    app = create_app(settings)

    with pytest.raises(OSError):
        async with app.router.lifespan_context(app):
            pytest.fail("Startup must not publish services after storage fails")

    assert app.state.services is None
    assert settings.data_dir.read_text() == "existing file"


async def test_partial_startup_releases_resources_without_publishing_services(
    settings: Settings,
) -> None:
    closed: list[str] = []

    async def close_async() -> None:
        assert app.state.services is None
        closed.append("async")

    async def factory(config: Settings, stack: AsyncExitStack) -> AppServices:
        stack.callback(closed.append, "sync")
        stack.push_async_callback(close_async)
        await build_services(config, stack)
        raise RuntimeError("later initialization failed")

    app = create_app(settings, services_factory=factory)
    with pytest.raises(RuntimeError, match="later initialization failed"):
        async with app.router.lifespan_context(app):
            pytest.fail("Incomplete services must not be published")

    assert app.state.services is None
    assert closed == ["async", "sync"]


@pytest.mark.parametrize("failure", [None, RuntimeError, asyncio.CancelledError])
async def test_shutdown_cleans_resources_and_preserves_knowledge_bases(
    settings: Settings, failure: type[BaseException] | None
) -> None:
    closed: list[str] = []

    async def close_async() -> None:
        assert app.state.services is None
        closed.append("async")

    async def factory(config: Settings, stack: AsyncExitStack) -> AppServices:
        services = await build_services(config, stack)
        stack.callback(closed.append, "sync")
        stack.push_async_callback(close_async)
        return services

    app = create_app(settings, services_factory=factory)
    expected = pytest.raises(failure, match="lifespan interrupted") if failure else nullcontext()
    with expected:
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver"
            ) as client:
                kb = await create_kb(client)
            if failure:
                raise failure("lifespan interrupted")

    assert app.state.services is None
    assert closed == ["async", "sync"]
    assert (settings.data_dir / "kbs" / kb["id"] / "manifest.json").exists()
    assert (settings.data_dir / "kbs" / kb["id"] / "vectors.pkl").exists()


async def test_shutdown_attempts_remaining_cleanup_after_failure(settings: Settings) -> None:
    closed: list[str] = []

    async def failing_close() -> None:
        assert app.state.services is None
        closed.append("failing")
        raise RuntimeError("cleanup failed")

    async def factory(config: Settings, stack: AsyncExitStack) -> AppServices:
        services = await build_services(config, stack)
        stack.callback(closed.append, "remaining")
        stack.push_async_callback(failing_close)
        return services

    app = create_app(settings, services_factory=factory)
    with pytest.raises(RuntimeError, match="cleanup failed"):
        async with app.router.lifespan_context(app):
            assert app.state.services is not None

    assert app.state.services is None
    assert closed == ["failing", "remaining"]


@pytest.mark.parametrize(
    ("method", "endpoint", "payload"),
    [
        ("GET", "/api/health", {}),
        ("GET", "/api/models/config", {}),
        ("GET", "/api/kb", {}),
        ("GET", "/api/kb/kb_missing", {}),
        ("POST", "/api/kb/kb_missing/query", {"question": "hello"}),
        ("POST", "/api/kb/kb_missing/query/stream", {"question": "hello"}),
        ("POST", "/api/chat", {"messages": [{"role": "user", "content": "hello"}]}),
        ("POST", "/api/chat/stream", {"messages": [{"role": "user", "content": "hello"}]}),
        ("POST", "/api/kb", {}),
    ],
)
async def test_service_endpoints_are_unavailable_outside_lifespan(
    app: FastAPI, method: str, endpoint: str, payload: dict
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        for phase in ("before startup", "after shutdown"):
            if endpoint == "/api/kb" and method == "POST":
                response = await client.post(
                    endpoint,
                    data={"name": "Unavailable", "embedding_model": "offline"},
                    files=[("files", ("notes.txt", b"hello", "text/plain"))],
                )
            else:
                response = await client.request(method, endpoint, json=payload or None)
            assert response.status_code == 503, phase
            assert response.json() == {"detail": "Application services are unavailable"}
            if phase == "before startup":
                async with app.router.lifespan_context(app):
                    assert (await client.get("/api/health")).status_code == 200


async def test_simultaneous_apps_isolate_storage_cors_and_dependency_overrides(
    settings_factory,
) -> None:
    first_settings = settings_factory(openai_model="first", cors_origins=["https://first.example"])
    second_settings = settings_factory(
        openai_model="second", cors_origins=["https://second.example"]
    )
    first = create_app(first_settings)
    second = create_app(second_settings)

    async with second.router.lifespan_context(second):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=second), base_url="http://second"
        ) as second_client:
            async with first.router.lifespan_context(first):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=first), base_url="http://first"
                ) as first_client:
                    assert first.state.services is not second.state.services
                    assert first.state.services.kb_store is not second.state.services.kb_store
                    assert first.dependency_overrides is not second.dependency_overrides
                    first_kb = await create_kb(first_client, b"first app evidence")
                    assert (await second_client.get("/api/kb")).json() == []

                    for suffix in ("", "/query", "/query/stream"):
                        endpoint = f"/api/kb/{first_kb['id']}{suffix}"
                        response = (
                            await second_client.post(endpoint, json={"question": "evidence?"})
                            if suffix
                            else await second_client.get(endpoint)
                        )
                        assert response.status_code == 404
                        assert response.json() == {"detail": "Knowledge base not found"}

                    second_kb = await create_kb(second_client, b"second app evidence")
                    assert [kb["id"] for kb in (await first_client.get("/api/kb")).json()] == [
                        first_kb["id"]
                    ]
                    for client, origin, other_origin in (
                        (first_client, "https://first.example", "https://second.example"),
                        (second_client, "https://second.example", "https://first.example"),
                    ):
                        for candidate, allowed in ((origin, True), (other_origin, False)):
                            response = await client.options(
                                "/api/kb",
                                headers={
                                    "Origin": candidate,
                                    "Access-Control-Request-Method": "GET",
                                },
                            )
                            assert (response.status_code == 200) is allowed
                            assert response.headers.get("access-control-allow-origin") == (
                                candidate if allowed else None
                            )

                    async def override_settings() -> Settings:
                        return first_settings.model_copy(update={"openai_model": "overridden"})

                    replacement_store = KBStore(settings_factory().data_dir)

                    async def override_store() -> KBStore:
                        return replacement_store

                    first.dependency_overrides[get_app_settings] = override_settings
                    first.dependency_overrides[get_kb_store] = override_store
                    assert (await first_client.get("/api/models/config")).json()["model"] == (
                        "overridden"
                    )
                    assert (await first_client.get("/api/kb")).json() == []
                    assert (await second_client.get("/api/models/config")).json()[
                        "model"
                    ] == "second"
                    assert [kb["id"] for kb in (await second_client.get("/api/kb")).json()] == [
                        second_kb["id"]
                    ]

            assert first.state.services is None
            assert (await second_client.get("/api/health")).json() == {"status": "ok"}
            assert [kb["id"] for kb in (await second_client.get("/api/kb")).json()] == [
                second_kb["id"]
            ]


@pytest.mark.parametrize("kind", ["chat", "chat/stream", "query", "query/stream"])
async def test_request_model_overrides_do_not_mutate_application_settings(
    app_client: httpx.AsyncClient, app: FastAPI, monkeypatch, kind: str
) -> None:
    recorded: list[Settings] = []

    def record_settings(config: Settings):
        recorded.append(config)
        return None

    monkeypatch.setattr(providers, "get_llm", record_settings)
    base = app.state.services.settings
    original = base.model_dump()
    if kind.startswith("query"):
        kb = await create_kb(app_client)
        endpoint = f"/api/kb/{kb['id']}/{kind}"
        payload = {"question": "evidence?"}
    else:
        endpoint = f"/api/{kind}"
        payload = {"messages": [{"role": "user", "content": "hello"}]}
    payload["model_config_override"] = {
        "model": "request-model",
        "base_url": "https://provider.example/v1",
        "api_key": "request-secret",
    }

    response = await app_client.post(endpoint, json=payload)

    assert response.status_code == 200
    assert len(recorded) == 1
    assert recorded[0] is not base
    assert recorded[0].openai_model == "request-model"
    assert recorded[0].openai_base_url == "https://provider.example/v1"
    assert recorded[0].openai_api_key.get_secret_value() == "request-secret"
    assert base.model_dump() == original
    assert (await app_client.get("/api/models/config")).json() == {
        "model": base.openai_model,
        "base_url": base.openai_base_url,
        "has_api_key": False,
    }
