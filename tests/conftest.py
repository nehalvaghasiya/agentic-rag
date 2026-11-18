"""Deterministic fixtures; no external LLM, cloud account, or Docker required."""

from pathlib import Path

import pytest

from agentic_rag.core.config import Settings
from agentic_rag.core.demo import seed
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.models.principal import Principal

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def principal() -> Principal:
    return Principal("demo-user", "demo-tenant", frozenset({"admin", "analyst"}))


@pytest.fixture
async def runtime() -> RuntimeFactory:
    stack = RuntimeFactory(Settings(environment="demo"))
    await seed(stack, ROOT / "datasets" / "demo")
    yield stack
    await stack.close()
