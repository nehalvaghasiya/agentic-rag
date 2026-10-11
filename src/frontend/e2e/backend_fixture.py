"""Test-only FastAPI entry point for browser journeys."""

from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import backend.config as config_module
import backend.llm as provider_module
from backend.config import Settings
from tests.support import ScriptedEmbedder, ScriptedLLM

FIXTURE_TEXT = Path(__file__).with_name("data").joinpath("browser-fixture.txt").read_text().strip()
REWRITTEN_QUERY = "browser harness disposable storage"
SCRIPTED_ANSWER = "Each browser test run uses disposable storage."


def _deny_inet_connection(sock: socket.socket, address: Any) -> None:
    del address
    if sock.family in (socket.AF_INET, socket.AF_INET6):
        raise RuntimeError("Outbound network access is forbidden in browser tests")
    raise RuntimeError("Unexpected socket connection in browser tests")


def _deny_inet_connection_ex(sock: socket.socket, address: Any) -> int:
    _deny_inet_connection(sock, address)
    raise AssertionError("unreachable")


def _deny_create_connection(*args: Any, **kwargs: Any) -> socket.socket:
    del args, kwargs
    raise RuntimeError("Outbound network access is forbidden in browser tests")


socket.socket.connect = _deny_inet_connection
socket.socket.connect_ex = _deny_inet_connection_ex
socket.create_connection = _deny_create_connection


def _scripted_llm(settings: Settings) -> ScriptedLLM:
    del settings
    return ScriptedLLM(
        invoke=[REWRITTEN_QUERY, "yes"],
        stream=["Each browser test ", "run uses disposable storage."],
    )


def _scripted_embedder(model_name: str, settings: Settings) -> ScriptedEmbedder:
    del model_name, settings
    return ScriptedEmbedder(
        {
            FIXTURE_TEXT: [1.0, 0.0],
            REWRITTEN_QUERY: [1.0, 0.0],
        }
    )


# Install all test seams before importing the module that constructs the global app.
provider_module.get_llm = _scripted_llm
provider_module.get_embedder = _scripted_embedder
config_module._settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

from backend.main import app

__all__ = ["SCRIPTED_ANSWER", "app"]
