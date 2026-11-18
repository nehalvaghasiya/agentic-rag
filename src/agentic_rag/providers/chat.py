"""Chat model boundary: grounded generation and structured tool calls."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from agentic_rag.models.action import Action
from agentic_rag.models.evidence import Evidence
from agentic_rag.models.grounded import GroundedAnswer
from agentic_rag.models.tool import ToolSpec


class ChatModel(Protocol):
    async def answer_document(
        self, messages: list[dict[str, str]], evidence: list[Evidence], *, instruction: str = ""
    ) -> GroundedAnswer: ...
    async def generate(self, question: str, evidence: list[Evidence]) -> str: ...
    async def choose_tools(
        self,
        question: str,
        tools: list[ToolSpec],
        prior: list[str],
        observations: list[dict[str, object]] | None = None,
    ) -> list[Action]: ...
    async def complete(
        self,
        messages: list[dict[str, str]],
        evidence: list[Evidence] | None = None,
        *,
        instruction: str = "",
        grounded: bool = False,
        json_output: bool = False,
        request_timeout: float | None = None,
    ) -> str: ...
    def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]: ...
    async def classify(
        self, text: str, has_kb: bool, history: list[dict[str, str]]
    ) -> dict[str, object]: ...
    async def assess(
        self,
        question: str,
        answer: str,
        evidence: list[Evidence],
        observations: list[dict[str, object]] | None = None,
    ) -> dict[str, object]: ...
