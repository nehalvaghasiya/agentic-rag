"""Deterministic scripted provider, used only by offline CI and demo."""

import re
from collections.abc import AsyncIterator

from agentic_rag.models.action import Action
from agentic_rag.models.evidence import Evidence
from agentic_rag.models.grounded import GroundedAnswer
from agentic_rag.models.tool import ToolSpec
from agentic_rag.search.keyword import tokens


class FakeChat:
    is_test_double = True

    async def answer_document(
        self, messages: list[dict[str, str]], evidence: list[Evidence], *, instruction: str = ""
    ) -> GroundedAnswer:
        answer = await self.complete(messages, evidence, grounded=True, instruction=instruction)
        return GroundedAnswer(answer, bool(evidence and "[source:" in answer))

    async def generate(self, question: str, evidence: list[Evidence]) -> str:
        if not evidence:
            return "I cannot answer from the available authorized sources."
        query_words = set(tokens(question)) - {
            "what",
            "is",
            "the",
            "of",
            "and",
            "in",
            "from",
            "a",
            "to",
            "how",
        }
        years = list(dict.fromkeys(re.findall(r"\b20\d{2}\b", question)))
        prioritized: list[Evidence] = []
        for year in years:
            match = next((e for e in evidence if year in e.text and e not in prioritized), None)
            if match:
                prioritized.append(match)
        prioritized.extend(e for e in evidence if e not in prioritized)
        cited: list[str] = []
        for item in prioritized[:3]:
            sentences = re.split(r"(?<=[.!?])\s+", item.text)
            ranked = sorted(sentences, key=lambda s: -len(query_words.intersection(tokens(s))))
            sentence = ranked[0].strip() if ranked else item.text[:180]
            if sentence:
                cited.append(f"{sentence} [source:{item.chunk_id}]")
        return "\n".join(cited)

    async def choose_tools(
        self,
        question: str,
        tools: list[ToolSpec],
        prior: list[str],
        observations: list[dict[str, object]] | None = None,
    ) -> list[Action]:
        available = {tool.name for tool in tools}
        lower = question.lower()
        actions: list[Action] = []
        if "time" in lower or "utc" in lower:
            actions.append(Action("time", {}))
        if "invoice" in lower or "revenue" in lower:
            op = "average" if "average" in lower else "count" if "count" in lower else "total"
            actions.append(Action("sql", {"operation": op}))
        if "calculate" in lower:
            match = re.search(r"(\d+(?:\.\d+)?)\s*([+*\-/])\s*(\d+(?:\.\d+)?)", question)
            if match:
                op = {"+": "add", "-": "subtract", "*": "multiply", "/": "divide"}[match[2]]
                actions.append(
                    Action(
                        "calculate", {"a": float(match[1]), "b": float(match[3]), "operation": op}
                    )
                )
        if (
            "calculate" in lower
            and "difference" in lower
            and observations
            and not any(a.tool == "calculate" for a in actions)
        ):
            passages: list[dict[str, object]] = []
            for observation in observations:
                output = observation.get("output")
                if isinstance(output, dict) and isinstance(output.get("passages"), list):
                    passages.extend(p for p in output["passages"] if isinstance(p, dict))
            years = set(re.findall(r"\b20\d\d\b", question))
            selected = [
                p for p in passages if any(year in str(p.get("title", "")) for year in years)
            ]
            days = [
                float(x)
                for p in selected
                for x in re.findall(r"refund window is (\d+) days", str(p.get("text", "")), re.I)
            ]
            if len(set(days)) >= 2:
                actions.append(
                    Action("calculate", {"a": max(days), "b": min(days), "operation": "subtract"})
                )
        if "documents" in lower and "listing" in available:
            actions.append(Action("listing", {}))
        if "search" in available and "search" not in prior:
            actions.append(Action("search", {"query": question}))
        return [
            action for action in actions if action.tool in available and action.tool not in prior
        ]

    async def complete(
        self,
        messages: list[dict[str, str]],
        evidence: list[Evidence] | None = None,
        *,
        instruction: str = "",
        grounded: bool = False,
        json_output: bool = False,
        request_timeout: float | None = None,
    ) -> str:
        question = messages[-1]["content"]
        if grounded:
            return await self.generate(question, evidence or [])
        if "Summarize" in instruction:
            return (
                "Conversation notes (scripted demo): "
                + " ".join(m["content"] for m in messages)[-3500:]
            )
        if "what is my name" in question.lower():
            names = re.findall(
                r"my name is ([\w-]+)", " ".join(m["content"] for m in messages), re.I
            )
            return (
                f"Your name is {names[-1]}."
                if names
                else "You have not told me your name in this chat."
            )
        if re.fullmatch(r"\s*(hi|hello|hey|thanks|thank you)[!.\s]*", question, re.I):
            return (
                "Hello! How can I help you?"
                if "thank" not in question.lower()
                else "You're welcome!"
            )
        return (
            "Scripted demo response: "
            + question
            + ". Configure a live model provider for general answers."
        )

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]:
        yield await self.complete(messages)

    async def classify(
        self, text: str, has_kb: bool, history: list[dict[str, str]]
    ) -> dict[str, object]:
        return {
            "mode": "baseline" if has_kb else "direct",
            "reason": "Scripted demo classification",
        }

    async def assess(
        self,
        question: str,
        answer: str,
        evidence: list[Evidence],
        observations: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        supported = bool(
            (evidence and "[source:" in answer)
            or (observations and any(o.get("status") == "ok" for o in observations))
        )
        return {
            "supported": supported,
            "complete": supported,
            "missing": "" if evidence else "No evidence",
            "conflict": False,
        }
