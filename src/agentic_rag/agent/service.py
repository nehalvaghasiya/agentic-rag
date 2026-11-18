"""One run lifecycle with direct, fast retrieval, and bounded agentic executors."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncIterator
from dataclasses import asdict, replace
from typing import Any
from uuid import uuid4

import httpx

from agentic_rag.agent.loop import LoopGuard
from agentic_rag.agent.plan import Planner
from agentic_rag.agent.research import ResearchAgent
from agentic_rag.agent.route import DOC, Router
from agentic_rag.agent.search import SearchAgent
from agentic_rag.agent.state import AgentState
from agentic_rag.agent.supervisor import Supervisor
from agentic_rag.agent.synth import Synthesizer
from agentic_rag.agent.verify import VerifyAgent
from agentic_rag.data.cache import Cache, fingerprint
from agentic_rag.data.repository import Repository
from agentic_rag.knowledge.intent import document_intent
from agentic_rag.memory.conversation import ConversationService, now
from agentic_rag.models.answer import Answer
from agentic_rag.models.budget import Budget
from agentic_rag.models.event import Event
from agentic_rag.models.evidence import Evidence
from agentic_rag.models.grounded import (
    DOCUMENT_PROMPT_RESERVE,
    GroundedAnswer,
    GroundingError,
    source_context_chars,
)
from agentic_rag.models.principal import Principal
from agentic_rag.models.query import Query
from agentic_rag.models.route import RouteDecision
from agentic_rag.models.run import Run
from agentic_rag.ops.metrics import Metrics
from agentic_rag.ops.trace import TraceService
from agentic_rag.providers.chat import ChatModel
from agentic_rag.search.citation import CitationValidator
from agentic_rag.search.documents import DocumentContext, DocumentProblem, DocumentReader
from agentic_rag.search.service import SearchService
from agentic_rag.skills.registry import SkillRegistry
from agentic_rag.tools.base import ToolContext
from agentic_rag.tools.registry import ToolRegistry
from agentic_rag.tools.runner import ToolRunner


class AgentService:
    def __init__(
        self,
        store: Repository,
        search: SearchService,
        chat: ChatModel,
        registry: ToolRegistry,
        *,
        skills: SkillRegistry | None = None,
        strict_graph: bool = False,
        metrics: Metrics | None = None,
        trace: TraceService | None = None,
        streaming: bool = True,
    ) -> None:
        self.store, self.search, self.chat, self.registry = store, search, chat, registry
        self.skills, self.streaming = skills, streaming
        self.trace = trace or TraceService()
        self.router, self.planner, self.supervisor = Router(), Planner(), Supervisor()
        self.runner = ToolRunner(registry, store, metrics=metrics, trace=self.trace)
        self.research = ResearchAgent(SearchAgent(self.runner, search), self.planner)
        self.synth, self.verifier = Synthesizer(chat), VerifyAgent(CitationValidator(search))
        self.sessions, self.cache = ConversationService(store, chat), Cache(store)
        self.documents = DocumentReader(store)
        self._document_context: dict[str, DocumentContext] = {}
        self._outcomes: dict[str, str] = {}
        self._queries: dict[str, Query] = {}
        self._budgets: dict[str, Budget] = {}
        self._guards: dict[str, LoopGuard] = {}
        self._supported: dict[str, bool] = {}
        self._limitations: dict[str, str] = {}
        self.graph: Any = None
        self.configure_graph()

    def configure_graph(self, checkpointer: Any = None) -> None:
        from agentic_rag.agent.graph import build_graph

        self.graph = build_graph(self, checkpointer)

    async def _log(self, run_id: str, kind: str, **data: Any) -> None:
        await self.store.log(run_id, kind, data, self._queries[run_id].principal)

    def _messages(self, query: Query) -> list[dict[str, str]]:
        return [*query.history, {"role": "user", "content": query.text}]

    @staticmethod
    def _draft_label(query: Query, text: str) -> str:
        if document_intent(query.text, bool(query.kb_ids)).operation in {
            "transform",
            "analysis",
        } and re.search(
            r"\b(?:create|draft|generate|prepare|build|convert|turn|make)\b", query.text, re.I
        ):
            return (
                "Proposed draft based on the document. Added scheduling, sequencing, or implementation choices are proposals, not stated document commitments.\n\n"
                + text
            )
        return text

    async def _call(self, run_id: str, operation: Any) -> Any:
        """Bounded retry only before an operation has returned output."""
        budget = self._budgets[run_id]
        for attempt in range(budget.max_retries + 1):
            try:
                return await operation()
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                retryable = not isinstance(
                    exc, httpx.HTTPStatusError
                ) or exc.response.status_code in {429, 502, 503, 504}
                if not retryable or attempt >= budget.max_retries:
                    raise
                await self._log(
                    run_id,
                    "retry",
                    title="Retrying provider request",
                    attempt=attempt + 1,
                    reason_code="PROVIDER_TIMEOUT"
                    if isinstance(exc, httpx.TimeoutException)
                    else "PROVIDER_RATE_LIMIT"
                    if exc.response.status_code == 429
                    else "PROVIDER_UNAVAILABLE",
                    description="The model provider did not respond before its timeout."
                    if isinstance(exc, httpx.TimeoutException)
                    else f"The model provider returned HTTP {exc.response.status_code}.",
                )
                await asyncio.sleep(min(0.25 * (2**attempt), 1.0))
        raise RuntimeError("Retry budget exhausted")

    async def _grounded(
        self,
        run_id: str,
        messages: list[dict[str, str]],
        evidence: list[Evidence],
        instruction: str = "",
    ) -> GroundedAnswer:
        remaining = (
            self._budgets[run_id].max_input_tokens * 4
            - source_context_chars(evidence)
            - len(instruction)
            - DOCUMENT_PROMPT_RESERVE
        )
        if not messages or len(messages[-1]["content"]) > remaining:
            raise DocumentProblem(
                "coverage_limit",
                "The document evidence and current question exceed the configured input budget. Ask about a narrower scope; no source passages were silently discarded.",
            )
        original_count = len(messages)
        messages = list(messages)
        while sum(len(message["content"]) for message in messages) > remaining:
            messages.pop(0)
        # Keep user/assistant history pairs rather than leaving a detached old assistant reply.
        while len(messages) > 1 and messages[0]["role"] == "assistant":
            messages.pop(0)
        if len(messages) != original_count:
            await self._log(
                run_id,
                "context",
                title="Conversation context adjusted for document reading",
                description="Older conversation turns were omitted to keep the complete document evidence and current question within the input budget.",
                retained_messages=len(messages),
            )
        validation_feedback = ""
        last_kind = "citation"
        for attempt in range(self._budgets[run_id].max_retries + 1):
            try:
                result: GroundedAnswer = await self._call(
                    run_id,
                    lambda feedback=validation_feedback: self.chat.answer_document(
                        messages, evidence, instruction=instruction + feedback
                    ),
                )
                if result.supported:
                    valid, _ = await self.verifier.check(
                        result.text, evidence, self._queries[run_id].principal
                    )
                    if not valid:
                        raise GroundingError("Document source references failed validation")
                elif result.text and not result.reason:
                    raise GroundingError("Missing document source references")
                return result
            except GroundingError as error:
                last_kind = error.kind
                validation_feedback = (
                    "\nThe previous output failed deterministic validation: "
                    + str(error)
                    + ". Return the complete corrected JSON in the requested schema."
                )
                await self._log(
                    run_id,
                    "verification",
                    title="Document answer validation failed",
                    reason_code="INVALID_DOCUMENT_FORMAT"
                    if error.kind == "format"
                    else "INVALID_SOURCE_REFERENCES",
                    description=str(error),
                )
                if attempt < self._budgets[run_id].max_retries:
                    await self._log(
                        run_id,
                        "retry",
                        title="Repairing requested document format"
                        if error.kind == "format"
                        else "Repairing document citations",
                        attempt=attempt + 1,
                    )
        self._outcomes[run_id] = (
            "verification_failed" if last_kind == "format" else "citation_error"
        )
        self._limitations[run_id] = (
            f"I read {len(evidence)} source passages, but the model did not produce the requested validated format after retrying. Please retry this question."
            if last_kind == "format"
            else f"I read {len(evidence)} source passages, but the model did not return valid source references after retrying. Please retry this question."
        )
        return GroundedAnswer("", False, self._limitations[run_id])

    async def _prepare_document(self, run_id: str) -> DocumentContext:
        async def generate(
            messages: list[dict[str, str]], evidence: list[Evidence], instruction: str
        ) -> GroundedAnswer:
            return await self._grounded(run_id, messages, evidence, instruction)

        async def emit(kind: str, **data: Any) -> None:
            await self._log(run_id, kind, **data)

        model_key = fingerprint(
            [
                type(self.chat).__name__,
                getattr(self.chat, "model", "fake"),
                getattr(self.chat, "base_url", ""),
            ]
        )
        context = await self.documents.prepare(self._queries[run_id], generate, emit, model_key)
        self._document_context[run_id] = context
        return context

    async def _assess(
        self,
        run_id: str,
        answer: str,
        evidence: list[Evidence],
        observations: list[dict[str, object]],
    ) -> dict[str, object]:
        for attempt in range(self._budgets[run_id].max_retries + 1):
            try:
                assessment: dict[str, object] = await self._call(
                    run_id,
                    lambda: self.chat.assess(
                        self._queries[run_id].text, answer, evidence, observations
                    ),
                )
                return assessment
            except ValueError:
                await self._log(
                    run_id,
                    "verification",
                    title="Support assessment could not be validated",
                    description="The provider returned an invalid structured verification result.",
                )
                if attempt < self._budgets[run_id].max_retries:
                    await self._log(
                        run_id,
                        "retry",
                        title="Retrying support assessment",
                        attempt=attempt + 1,
                    )
        self._limitations[run_id] = (
            "The model's verification response could not be validated. Please retry this question."
        )
        return {"supported": False, "missing": "Verification unavailable"}

    async def plan_node(self, state: AgentState) -> AgentState:
        run_id = state["run_id"]
        query = self._queries[run_id]
        plan = self.planner.plan(query.text)
        whole_document = (
            bool(query.kb_ids)
            and document_intent(query.text, True).broad
            and plan.skill not in {"calculate", "sql", "time"}
        )
        await self._log(run_id, "plan", title="Preparing evidence plan")
        if query.kb_ids and plan.skill in {"calculate", "sql"} and DOC.search(query.text):
            plan = replace(plan, skill="research")
        goals = list(plan.goals)
        if whole_document:
            goals = [
                "Read every current authorized passage in the selected document scope.",
                "Produce the requested output with source attribution and the required structure.",
                "Verify source constraints, factual support and completion of the requested task.",
            ]
            plan = replace(plan, skill="research")
        # The deterministic planner is a bounded fallback; live providers may refine goals.
        if not whole_document and not getattr(self.chat, "is_test_double", False):
            try:
                raw = await self._call(
                    run_id,
                    lambda: self.chat.complete(
                        self._messages(query),
                        instruction='Create an evidence collection plan. Return only JSON {"goals":["standalone evidence question"],"requires_retrieval":true|false}. '
                        "Use at most three independent goals. Preserve document identifiers, dates, filters and comparison targets. "
                        f"A knowledge base is {'attached' if query.kb_ids else 'not attached'}. "
                        "Set requires_retrieval to true when inputs must come from the attached knowledge base, "
                        "and false for self-contained calculations or general knowledge. "
                        "Do not answer the question or include internal reasoning.",
                        json_output=True,
                    ),
                )
                parsed = json.loads(raw.removeprefix("```json").removesuffix("```").strip())
                if isinstance(parsed, dict) and isinstance(parsed.get("goals"), list):
                    selected = [
                        g[:1000] for g in parsed["goals"] if isinstance(g, str) and g.strip()
                    ][:3]
                    if selected:
                        goals = selected
                    if (
                        query.kb_ids
                        and plan.skill == "calculate"
                        and parsed.get("requires_retrieval") is True
                    ):
                        plan = replace(plan, skill="research")
            except (ValueError, KeyError):
                await self._log(
                    run_id,
                    "plan",
                    title="Using bounded fallback plan",
                    description="The provider did not return a valid structured plan.",
                )
        await self._log(
            run_id,
            "plan",
            title="Evidence plan",
            skill=plan.skill,
            goals=goals,
            description="Whole-document coverage determines the evidence plan; no extra planning-model request is needed."
            if whole_document
            else f"{len(goals)} bounded task(s)",
            plan_method="whole_document_policy" if whole_document else "bounded_planner",
        )
        return {
            "goals": goals,
            "skill": plan.skill,
            "iteration": 0,
            "evidence_ids": [],
            "observations": [],
        }

    async def research_node(self, state: AgentState) -> AgentState:
        run_id = state["run_id"]
        query, budget = self._queries[run_id], self._budgets[run_id]
        run = await self.store.get_run(run_id, query.principal)
        if run.status == "cancelled":
            raise asyncio.CancelledError
        if run.steps >= budget.max_steps:
            await self._log(run_id, "budget", title="Step limit reached", reason="steps")
            return {"iteration": state.get("iteration", 0) + 1}
        if document_intent(query.text, bool(query.kb_ids)).broad and self.planner.plan(
            query.text
        ).skill not in {"calculate", "sql", "time"}:
            aid = uuid4().hex
            await self._log(
                run_id,
                "agent_started",
                title="Research specialist reading complete document",
                name="ResearchAgent",
                activity_id=aid,
            )
            try:
                context = self._document_context.get(run_id) or await self._prepare_document(run_id)
            finally:
                await self._log(
                    run_id,
                    "agent_finished",
                    title="Research specialist document read finished",
                    name="ResearchAgent",
                    activity_id=aid,
                )
            run.steps += 1
            run.coverage = context.coverage
            run.evidence_count = int(context.coverage["read_chunks"])
            await self.store.save_run(run, query.principal)
            return {
                "evidence_ids": [e.chunk_id for e in context.evidence],
                "iteration": state.get("iteration", 0) + 1,
            }
        route = self.router.route(query.text, has_kb=bool(query.kb_ids))
        worker = self.supervisor.next(
            route, bool(state.get("evidence_ids")), run.steps, budget.max_steps
        )
        await self._log(run_id, "plan", title="Supervisor selected next task", worker=worker)
        ids = set(state.get("evidence_ids", []))
        observations = list(state.get("observations", []))
        tool_skill = self.planner.plan(query.text).skill
        mixed_tools = state.get("skill") == "research" and tool_skill in {
            "calculate",
            "sql",
            "time",
        }
        goals = [state["missing"]] if state.get("missing") else state.get("goals", [query.text])
        if query.kb_ids and state.get("skill") not in {"sql", "calculate", "time", "listing"}:
            remaining = max(0, budget.max_tool_calls - self.runner.counts.get(run_id, 0))
            goals = [g for g in goals if not self._guards[run_id].detect("search", {"query": g})][
                :remaining
            ]
            if goals:
                evidence = await self.research.work(
                    query, run_id, replace(budget, max_tool_calls=budget.max_tool_calls), goals
                )
                ids.update(e.chunk_id for e in evidence)
                if mixed_tools:
                    observations.append(
                        {
                            "tool": "search",
                            "status": "ok",
                            "output": {
                                "passages": [
                                    {"id": e.chunk_id, "text": e.text, "title": e.title}
                                    for e in evidence
                                ]
                            },
                        }
                    )
        if (
            (not query.kb_ids and tool_skill in {"sql", "calculate", "time", "listing"})
            or state.get("skill") in {"sql", "calculate", "time", "listing"}
            or mixed_tools
        ):
            allowed = [
                self.registry.get(str(t["name"])).spec
                for t in self.registry.list()
                if t["risk"] == "read"
                and self.registry.get(str(t["name"])).spec.scopes.issubset(query.principal.roles)
                and (query.kb_ids or t["name"] not in {"search", "lookup", "listing"})
            ]
            if self.skills:
                try:
                    skill = self.skills.get(
                        tool_skill if mixed_tools else state.get("skill", "lookup"),
                        {t.name for t in allowed},
                    )
                    allowed = [t for t in allowed if t.name in skill.tools]
                except PermissionError:
                    allowed = []
                    self._limitations[run_id] = (
                        "The required tool is not configured or authorized for this chat. Attach the relevant knowledge base or configure the approved dataset on the server."
                    )
                    await self._log(
                        run_id,
                        "tool_denied",
                        title="Required tool unavailable",
                        description=self._limitations[run_id],
                    )
            if allowed:
                aid = uuid4().hex
                await self._log(
                    run_id,
                    "agent_started",
                    title="Tool specialist started",
                    name="ToolAgent",
                    activity_id=aid,
                )
                try:
                    prior = [str(o.get("tool")) for o in observations]
                    actions = await self._call(
                        run_id,
                        lambda: self.chat.choose_tools(query.text, allowed, prior, observations),
                    )
                    for action in actions:
                        if action.tool not in {t.name for t in allowed}:
                            await self._log(
                                run_id,
                                "tool_denied",
                                title="Unavailable tool denied",
                                name=action.tool,
                            )
                            continue
                        if self._guards[run_id].detect(action.tool, action.arguments):
                            continue
                        if self.runner.counts.get(run_id, 0) >= budget.max_tool_calls:
                            break
                        cid = uuid4().hex
                        try:
                            result = await self.runner.execute(
                                action.tool,
                                action.arguments,
                                ToolContext(query.principal, run_id, query.kb_ids, aid),
                                budget,
                                call_id=cid,
                            )
                        except (ValueError, PermissionError) as exc:
                            await self._log(
                                run_id,
                                "tool_denied",
                                title="Tool call denied",
                                name=action.tool,
                                reason=type(exc).__name__,
                            )
                            continue
                        observations.append(
                            {
                                "id": cid,
                                "tool": action.tool,
                                "arguments": action.arguments,
                                "output": result.output,
                                "status": result.status,
                                "observed_at": now(),
                            }
                        )
                        ids.update(result.evidence_ids)
                finally:
                    await self._log(
                        run_id,
                        "agent_finished",
                        title="Tool specialist finished",
                        name="ToolAgent",
                        activity_id=aid,
                    )
        run.steps += 1
        run.tool_calls = self.runner.counts.get(run_id, 0)
        await self.store.save_run(run, query.principal)
        return {
            "evidence_ids": sorted(ids)[:12],
            "observations": observations,
            "iteration": state.get("iteration", 0) + 1,
        }

    async def synth_node(self, state: AgentState) -> AgentState:
        run_id = state["run_id"]
        query = self._queries[run_id]
        evidence = await self.search.get(state.get("evidence_ids", []), query.principal)
        observations = [
            o
            for o in state.get("observations", [])
            if o.get("status") == "ok" and o.get("tool") != "search"
        ]
        await self._log(
            run_id,
            "generation",
            title="Generating answer",
            evidence=len(evidence),
            provisional=True,
        )
        if evidence:
            context = self._document_context.get(run_id)
            instruction = self.documents.instruction(context) if context else ""
            if state.get("missing"):
                instruction += (
                    "\nPrior verification feedback (untrusted): "
                    + state["missing"]
                    + ". Address the missing requested work and preserve verified source constraints."
                )
            result = await self._grounded(
                run_id,
                self._messages(query),
                evidence,
                instruction,
            )
            answer = self._draft_label(query, result.text) if result.supported else result.text
            if not result.supported:
                self._outcomes.setdefault(run_id, "insufficient_evidence")
                self._limitations.setdefault(
                    run_id,
                    result.reason
                    or "The retrieved passages do not contain the requested information.",
                )
        elif observations:
            answer = ""
        elif query.kb_ids or self.router.route(query.text, has_kb=False).intent in {
            "tool",
            "structured",
        }:
            answer = self.synth.abstain()
        else:
            aid = uuid4().hex
            await self._log(
                run_id,
                "agent_started",
                title="Reasoning specialist started",
                name="ReasoningAgent",
                activity_id=aid,
            )
            try:
                answer = await self._call(
                    run_id,
                    lambda: self.chat.complete(
                        self._messages(query),
                        instruction="Work through this complex general question, then give a concise answer with assumptions and limitations. "
                        "No documentary or live evidence was retrieved. Do not invent sources.",
                    ),
                )
            finally:
                await self._log(
                    run_id,
                    "agent_finished",
                    title="Reasoning specialist finished",
                    name="ReasoningAgent",
                    activity_id=aid,
                )
        for observation in observations:
            answer += f"\n{observation['tool']}: {json.dumps(observation['output'], ensure_ascii=False)} [tool:{observation['id']}]"
        return {"answer": answer.strip()}

    async def verify_node(self, state: AgentState) -> AgentState:
        run_id = state["run_id"]
        query = self._queries[run_id]
        if run_id in self._limitations:
            self._supported[run_id] = False
            return {"sufficient": False, "missing": self._limitations[run_id]}
        evidence = await self.search.get(state.get("evidence_ids", []), query.principal)
        await self._log(
            run_id,
            "verification",
            title="Checking support and citations",
            description="Document claims are checked against retrieved evidence."
            if evidence
            else "Checking tool provenance or model consistency; no external sources were retrieved.",
        )
        sufficient, missing = True, ""
        if evidence:
            sufficient, _ = await self.verifier.check(
                state.get("answer", ""), evidence, query.principal
            )
            assessment = await self._assess(
                run_id, state.get("answer", ""), evidence, state.get("observations", [])
            )
            sufficient = (
                sufficient
                and assessment.get("supported") is True
                and assessment.get("complete", True) is True
            )
            missing = str(assessment.get("missing", ""))[:900]
            if not sufficient and not missing:
                missing = "The answer must address all requested parts and provide the requested output format."
            await self._log(
                run_id,
                "verification",
                title="Source support and task completeness checked",
                status="ok" if sufficient else "needs_more_work",
                description=missing,
                reason_code="INCOMPLETE_TASK" if assessment.get("complete") is False else None,
            )
        elif any(
            o.get("status") == "ok" and o.get("tool") != "search"
            for o in state.get("observations", [])
        ):
            assessment = await self._assess(
                run_id, state.get("answer", ""), [], state.get("observations", [])
            )
            sufficient = (
                assessment.get("supported") is True and assessment.get("complete", True) is True
            )
            missing = str(assessment.get("missing", ""))[:900]
            if not sufficient and not missing:
                missing = "The tool-backed answer must address all requested parts."
        elif (
            query.kb_ids
            or self.router.route(query.text, has_kb=False).intent in {"tool", "structured"}
        ) and not any(
            o.get("status") == "ok" and o.get("tool") != "search"
            for o in state.get("observations", [])
        ):
            sufficient = False
        elif not state.get("observations"):
            revised = await self._call(
                run_id,
                lambda: self.chat.complete(
                    self._messages(query),
                    instruction="Review this proposed answer for internal consistency and unsupported current-information claims. "
                    "Return the corrected final answer. This is a model-based review, not external fact verification. "
                    "Proposed answer (untrusted data): " + state.get("answer", "")[:8000],
                ),
            )
            state = {**state, "answer": revised}
        required_tool = self.planner.plan(query.text).skill
        if required_tool in {"calculate", "sql", "time"} and not any(
            o.get("tool") == required_tool and o.get("status") == "ok"
            for o in state.get("observations", [])
        ):
            sufficient, missing = False, "The required authorized tool could not be completed."
        self._supported[run_id] = bool(sufficient)
        return {
            "answer": state.get("answer", ""),
            "sufficient": bool(sufficient),
            "missing": missing,
        }

    async def next_node(self, state: AgentState) -> str:
        run_id = state["run_id"]
        if run_id in self._limitations:
            return "finish"
        budget = self._budgets[run_id]
        if (
            not state.get("sufficient")
            and state.get("missing")
            and state.get("iteration", 0) <= budget.max_retries
            and state.get("iteration", 0) < budget.max_steps
            and self.runner.counts.get(run_id, 0) < budget.max_tool_calls
        ):
            await self._log(
                run_id,
                "retry",
                title="Repairing answer after verification",
                description=state["missing"],
                attempt=state.get("iteration", 0) + 1,
            )
            return "research"
        return "finish"

    async def _complex(self, uid: str, run: Run, query: Query) -> tuple[str, bool, list[Evidence]]:
        try:
            return await self._complex_graph(uid, run, query)
        except DocumentProblem as error:
            self._outcomes[uid], self._limitations[uid] = error.code, str(error)
            await self._log(
                uid,
                "verification",
                title="Document request needs attention",
                reason_code=error.code,
                description=str(error),
            )
            return "", False, []

    async def _complex_graph(
        self, uid: str, run: Run, query: Query
    ) -> tuple[str, bool, list[Evidence]]:
        state = await self.graph.ainvoke(
            {"run_id": uid},
            config={
                "configurable": {
                    "thread_id": f"{query.principal.tenant_id}:{query.principal.user_id}:{uid}"
                },
                "recursion_limit": 30,
            },
        )
        evidence = await self.search.get(state.get("evidence_ids", []), query.principal)
        answer, supported = state.get("answer", ""), self._supported.get(uid, False)
        if not supported and state.get("missing") and uid not in self._limitations:
            self._outcomes[uid] = "verification_failed"
            self._limitations[uid] = (
                "I could not produce a complete, supported answer within this run's limits. "
                + state["missing"]
            )
        if context := self._document_context.get(uid):
            run.coverage = context.coverage
            run.evidence_count = int(context.coverage["read_chunks"])
        else:
            run.evidence_count = len(evidence)
        run.grounding = (
            "documents" if evidence else "tools" if state.get("observations") else "model"
        )
        for observation in state.get("observations", []):
            if observation.get("status") == "ok" and observation.get("tool") != "search":
                run.sources.append(
                    {
                        "id": str(observation["id"]),
                        "kind": "tool",
                        "title": str(observation["tool"]),
                        "tool": str(observation["tool"]),
                        "excerpt": json.dumps(observation["output"], ensure_ascii=False)[:2000],
                        "observed_at": str(observation["observed_at"]),
                        "available": True,
                    }
                )
        if evidence and run.sources:
            run.grounding = "mixed"
        return answer, supported, evidence

    async def _document_request(
        self, uid: str, run: Run, query: Query
    ) -> tuple[str, bool, list[Evidence]]:
        run.grounding = "documents"
        try:
            context = await self._prepare_document(uid)
            run.coverage = context.coverage
            run.evidence_count = int(context.coverage["read_chunks"])
            await self._log(
                uid,
                "generation",
                title="Answering the document request",
                description="Using the requested format and structured source attribution.",
            )
            result = await self._grounded(
                uid, self._messages(query), context.evidence, self.documents.instruction(context)
            )
            if not result.supported:
                self._outcomes.setdefault(uid, "insufficient_evidence")
                self._limitations.setdefault(
                    uid, result.reason or "The document does not contain the requested information."
                )
            await self._log(
                uid,
                "verification",
                title="Document answer attribution checked",
                status="ok" if result.supported else "unsupported",
                reason_code=self._outcomes.get(uid),
                description=result.reason,
            )
            return (
                self._draft_label(query, result.text) if result.supported else result.text,
                result.supported,
                context.evidence,
            )
        except DocumentProblem as error:
            self._outcomes.setdefault(uid, error.code)
            self._limitations.setdefault(uid, str(error))
            await self._log(
                uid,
                "verification",
                title="Document request needs attention",
                reason_code=error.code,
                description=str(error),
            )
            return "", False, []

    async def _lookup(
        self, uid: str, run: Run, query: Query, mode: str
    ) -> tuple[str, bool, list[Evidence]]:
        strategy = "dense" if run.mode == "baseline" else "advanced"
        await self._log(
            uid, "retrieval_started", title="Retrieving document passages", strategy=strategy
        )
        evidence = await self.search.search(
            query, strategy=strategy, limit=4 if run.mode == "baseline" else 6
        )
        run.grounding, run.evidence_count = "documents", len(evidence)
        run.coverage = {
            "documents": list(dict.fromkeys(e.title for e in evidence)),
            "read_chunks": len(evidence),
            "total_chunks": 0,
            "strategy": "lookup",
        }
        await self._log(
            uid,
            "retrieval",
            title="Retrieval finished",
            count=len(evidence),
            strategy=strategy,
            coverage=run.coverage,
        )
        if (
            mode == "auto"
            and len({e.document_id for e in evidence}) > 1
            and re.search(r"\b(why|explain)\b", query.text, re.I)
            and re.search(
                r"\b(change|changed|extended|reduced|conflict|inconsistent)\b", query.text, re.I
            )
        ):
            run.mode, run.execution_path = "agentic", "agentic"
            run.route_reason = (
                "Retrieved evidence requires explaining changes across multiple sources"
            )
            await self._log(
                uid,
                "escalation",
                title="Escalating to agentic research",
                description=run.route_reason,
            )
            await self._log(
                uid,
                "route",
                title="Agentic RAG",
                execution_path="agentic",
                mode="agentic",
                reason=run.route_reason,
            )
            await self.store.save_run(run, query.principal)
            return await self._complex(uid, run, query)
        if not evidence:
            self._outcomes[uid] = "insufficient_evidence"
            self._limitations[uid] = (
                "No matching indexed passages were found in the attached knowledge base. Ask for an overview to read the whole document, or check that its status is Indexed."
            )
            await self._log(
                uid,
                "verification",
                title="No matching indexed passages",
                reason_code="NO_MATCHING_PASSAGES",
                description=self._limitations[uid],
            )
            return "", False, []
        await self._log(uid, "generation", title="Generating grounded answer")
        result = await self._grounded(uid, self._messages(query), evidence)
        if not result.supported:
            self._outcomes.setdefault(uid, "insufficient_evidence")
            self._limitations.setdefault(
                uid,
                result.reason or "The retrieved passages do not contain the requested information.",
            )
        await self._log(
            uid,
            "verification",
            title="Validating citation identifiers and source access",
            status="ok" if result.supported else "unsupported",
            reason_code=self._outcomes.get(uid),
            description=result.reason,
        )
        return result.text, result.supported, evidence

    async def run(
        self,
        query: Query,
        *,
        mode: str = "auto",
        budget: Budget | None = None,
        run_id: str | None = None,
    ) -> Answer:
        if not query.text.strip() or len(query.text) > 4000:
            raise ValueError("Question must contain 1–4000 characters")
        for kb_id in query.kb_ids:
            await self.store.check_kb(kb_id, query.principal)
        if query.session_id:
            await self.store.get_session(query.session_id, query.principal)
        if run_id:
            run = await self.store.get_run(run_id, query.principal)
            if run.status != "pending":
                raise ValueError("Duplicate run ID")
        else:
            run = Run(
                uuid4().hex,
                query.principal.tenant_id,
                query.principal.user_id,
                mode=mode,
                requested_mode=mode,
                session_id=query.session_id,
                created_at=now(),
                kb_ids=list(query.kb_ids),
            )
            message = (
                {
                    "id": uuid4().hex,
                    "role": "user",
                    "content": query.text,
                    "status": "completed",
                    "run_id": run.id,
                    "created_at": run.created_at,
                    "sources": [],
                }
                if query.session_id
                else None
            )
            run, _ = await self.store.begin_run(
                run, message, fingerprint([query.text, mode]), query.principal
            )
        uid = run.id
        begun = time.monotonic()
        getattr(self.chat, "reset_usage", lambda: None)()
        self._queries[uid], self._budgets[uid], self._guards[uid] = (
            query,
            budget or Budget(),
            LoopGuard(),
        )
        run.status, run.model = "running", str(getattr(self.chat, "model", "scripted-demo"))
        await self.store.save_run(run, query.principal)
        await self._log(uid, "started", title="Request started", requested_mode=mode)
        try:
            async with asyncio.timeout(self._budgets[uid].max_seconds) as run_timeout:
                history, context_info = await self.sessions.context(
                    query.session_id, query.principal, uid
                )
                if query.history:
                    history = list(query.history)[-16:]
                resolved, clarification = self.sessions.resolve(
                    query.text, history, bool(query.kb_ids)
                )
                query = replace(
                    query,
                    text=resolved,
                    history=tuple(history),
                    filters={**query.filters, "run_id": uid},
                )
                self._queries[uid] = query
                await self._log(
                    uid, "context", title="Conversation context prepared", **context_info
                )
                route = self.router.route(query.text, mode, bool(query.kb_ids))
                required = self.router.route(query.text, "auto", bool(query.kb_ids))
                if required.intent in {"missing_knowledge", "live_unavailable"}:
                    route = required
                method = "rules"
                if route.intent == "uncertain":
                    method = "model"
                    await self._log(
                        uid,
                        "route",
                        title="Classifying source requirement",
                        classifier="model",
                        mode="pending",
                    )
                    try:
                        async with asyncio.timeout(5):
                            classified = await self.chat.classify(
                                query.text, bool(query.kb_ids), history
                            )
                    except (ValueError, TimeoutError, httpx.HTTPError):
                        await self._log(
                            uid,
                            "route",
                            title="Source classification unavailable",
                            reason_code="CLASSIFICATION_UNAVAILABLE",
                            description="The bounded classifier could not decide reliably; asking for source preference.",
                        )
                        classified = {
                            "mode": "clarify",
                            "reason": "The source requirement could not be classified reliably",
                        }
                    chosen = str(classified["mode"])
                    if chosen == "clarify":
                        clarification = (
                            "Should I answer generally or use the attached knowledge base?"
                        )
                        chosen = "direct"
                    route = RouteDecision(
                        chosen,
                        "classified",
                        0.0,
                        str(classified.get("reason", "Structured classification"))[:200],
                    )
                if clarification:
                    route = RouteDecision(
                        "direct", "clarify", 1.0, "Clarification needed before execution"
                    )
                if (
                    budget is None
                    and route.mode == "agentic"
                    and query.kb_ids
                    and document_intent(query.text, True).broad
                ):
                    self._budgets[uid] = replace(self._budgets[uid], max_seconds=180.0)
                    remaining = max(0.0, 180.0 - (time.monotonic() - begun))
                    run_timeout.reschedule(asyncio.get_running_loop().time() + remaining)
                    await self._log(
                        uid,
                        "budget",
                        title="Complex document analysis budget",
                        description="Allowing up to 180 seconds for complete document synthesis and source/task verification.",
                        max_seconds=180.0,
                    )
                if route.mode == "agentic" and required.intent in {
                    "general",
                    "conversation",
                    "general_complex",
                }:
                    self._queries[uid] = replace(query, kb_ids=())
                run.mode, run.route_reason = route.mode, route.reason
                run.execution_path = "rag" if route.mode in {"baseline", "advanced"} else route.mode
                await self._log(
                    uid,
                    "route",
                    title={"direct": "Direct LLM", "rag": "Fast RAG", "agentic": "Agentic RAG"}[
                        run.execution_path
                    ],
                    mode=run.mode,
                    execution_path=run.execution_path,
                    reason=route.reason,
                    classifier=method,
                    description=route.reason,
                    confidence_is_calibrated=False,
                )
                await self.store.save_run(run, query.principal)
                revision = (
                    await self.store.revision(query.kb_ids, query.principal)
                    if run.execution_path == "rag"
                    else ""
                )
                key = "answer:" + fingerprint(
                    [
                        query.text,
                        history,
                        sorted(query.kb_ids),
                        revision,
                        run.model,
                        type(self.chat).__name__,
                        getattr(self.chat, "base_url", ""),
                        run.mode,
                        sorted(query.principal.roles),
                        sorted(query.principal.groups),
                        "document-chat-v2",
                    ]
                )
                eligible = (
                    run.mode != "agentic"
                    and not run.regeneration_of_run_id
                    and route.intent not in {"missing_knowledge", "live_unavailable", "clarify"}
                    and mode == "auto"
                )
                cached = await self.cache.get(key, query.principal) if eligible else None
                if cached:
                    checked = await self.sessions.sanitize_sources(
                        cached.get("sources", []), query.principal
                    )
                    if any(not s.get("available", True) for s in checked):
                        cached = None
                await self._log(
                    uid,
                    "cache",
                    title="Response cache",
                    layer="response",
                    status="hit" if cached else "miss" if eligible else "bypass",
                    origin_run_id=cached.get("run_id") if cached else None,
                )
                evidence: list[Evidence] = []
                supported = True
                if cached:
                    run.answer, run.sources = cached["answer"], cached["sources"]
                    run.citations, supported = cached["citations"], cached["supported"]
                    run.served_from_cache, run.origin_run_id = True, cached["run_id"]
                    run.grounding = cached["grounding"]
                    run.evidence_count = cached.get("evidence_count", len(run.sources))
                    run.coverage = cached.get("coverage", {})
                else:
                    if clarification:
                        answer, run.grounding = clarification, "clarification"
                        run.answer_status = "clarification"
                    elif route.intent == "missing_knowledge":
                        answer, run.grounding = (
                            "Please attach the knowledge base containing that document so I can answer with citations.",
                            "clarification",
                        )
                        run.answer_status = "clarification"
                    elif route.intent == "live_unavailable":
                        answer, run.grounding = (
                            "Live web research is not configured. Please provide a current source or attach the relevant documents so I can verify this.",
                            "unavailable",
                        )
                    elif run.mode == "direct":
                        run.grounding = "model"
                        await self._log(
                            uid,
                            "generation",
                            title="Generating conversational answer",
                            model=run.model,
                        )
                        if self.streaming:
                            parts, pending = [], ""
                            async for token in self.chat.stream(self._messages(query)):
                                parts.append(token)
                                pending += token
                                if len(pending) >= 60:
                                    await self._log(uid, "token", token=pending)
                                    pending = ""
                            if pending:
                                await self._log(uid, "token", token=pending)
                            answer = "".join(parts)
                        else:
                            answer = await self._call(
                                uid, lambda: self.chat.complete(self._messages(query))
                            )
                    elif run.mode in {"baseline", "advanced"}:
                        if document_intent(query.text, bool(query.kb_ids)).broad:
                            answer, supported, evidence = await self._document_request(
                                uid, run, query
                            )
                        else:
                            answer, supported, evidence = await self._lookup(uid, run, query, mode)
                    else:
                        answer, supported, evidence = await self._complex(uid, run, query)
                    run.answer_status = self._outcomes.get(uid, run.answer_status)
                    if not supported:
                        if run.answer_status == "answered":
                            run.answer_status = "insufficient_evidence"
                        answer = self._limitations.get(
                            uid,
                            "The retrieved passages do not contain enough information to answer this question. Try a specific section or ask for a whole-document overview.",
                        )
                        run.sources = []
                    # Validate the actual citation set, then number only citations present in the answer.
                    cited = list(dict.fromkeys(re.findall(r"\[source:([a-f0-9]{24})\]", answer)))
                    allowed = {e.chunk_id: e for e in await self.search.get(cited, query.principal)}
                    if any(cid not in allowed for cid in cited):
                        answer, cited, supported, run.sources = self.synth.abstain(), [], False, []
                    docs = [
                        {
                            "id": cid,
                            "kind": "document",
                            "title": allowed[cid].title,
                            "document_id": allowed[cid].document_id,
                            "version": allowed[cid].version,
                            "page": allowed[cid].page,
                            "section": allowed[cid].section,
                            "excerpt": allowed[cid].text[:800],
                            "available": True,
                        }
                        for cid in cited
                    ]
                    run.sources = docs + run.sources
                    for index, source in enumerate(run.sources, 1):
                        marker = "source" if source["kind"] == "document" else "tool"
                        answer = answer.replace(f"[{marker}:{source['id']}]", f"[{index}]")
                    run.answer, run.citations = answer, cited
                    if eligible and supported and run.mode != "agentic":
                        await self.cache.put(
                            key,
                            {
                                "answer": answer,
                                "sources": run.sources,
                                "citations": cited,
                                "supported": supported,
                                "run_id": uid,
                                "grounding": run.grounding,
                                "evidence_count": run.evidence_count,
                                "coverage": run.coverage,
                                "session_id": query.session_id,
                            },
                            query.principal,
                        )
                if query.session_id:
                    session = await self.store.context_session(query.session_id, query.principal)
                    if len(session["messages"]) >= 16:
                        session["summary_status"] = "queued"
                        await self.store.save_session(session, query.principal)
                        await self._log(
                            uid,
                            "context",
                            title="History compression scheduled",
                            description="Earlier turns will be summarized in the background.",
                            summary_scheduled=True,
                        )
                run.status = "completed"
                run.tool_calls = self.runner.counts.get(uid, 0)
                if run.mode == "agentic":
                    current = await self.store.get_run(uid, query.principal)
                    run.steps = current.steps
                run.latency_ms = (time.monotonic() - begun) * 1000
                run.usage = {
                    "cost_usd": None,
                    "provider_usage": getattr(self.chat, "usage", lambda: None)(),
                    "input_tokens_estimate": sum(len(m["content"]) for m in self._messages(query))
                    // 4,
                    "output_tokens_estimate": len(run.answer) // 4,
                }
                data = {**asdict(run), "supported": supported, "finished_at": now()}
                if not await self.store.finish(run, "complete", data, query.principal):
                    raise asyncio.CancelledError
                return Answer(
                    run.answer,
                    tuple(run.citations),
                    supported,
                    uid,
                    run.mode,
                    tuple(e.chunk_id for e in evidence),
                )
        except (Exception, asyncio.CancelledError) as exc:
            cancelled = isinstance(exc, asyncio.CancelledError)
            current = await self.store.get_run(uid, query.principal)
            run.coverage = run.coverage or current.coverage
            run.evidence_count = max(run.evidence_count, current.evidence_count)
            run.steps = max(run.steps, current.steps)
            run.tool_calls = self.runner.counts.get(uid, current.tool_calls)
            run.latency_ms = (time.monotonic() - begun) * 1000
            run.answer_status = "verification_failed"
            run.usage = {
                "cost_usd": None,
                "provider_usage": getattr(self.chat, "usage", lambda: None)(),
            }
            code = "CANCELLED" if cancelled else "RUN_FAILED"
            failure_message = (
                "Response cancelled."
                if cancelled
                else "The response could not be completed. You can retry this message."
            )
            if isinstance(exc, TimeoutError):
                code, failure_message = (
                    "BUDGET_EXHAUSTED",
                    f"The response exceeded its {self._budgets[uid].max_seconds:g}-second limit. Please retry, or ask for a narrower scope.",
                )
            elif isinstance(exc, httpx.TimeoutException):
                code, failure_message = (
                    "PROVIDER_TIMEOUT",
                    "The model provider did not respond in time. Please retry this message.",
                )
            elif isinstance(exc, httpx.HTTPStatusError):
                status = exc.response.status_code
                code = (
                    "PROVIDER_RATE_LIMIT"
                    if status == 429
                    else "PROVIDER_UNAVAILABLE"
                    if status >= 500
                    else "PROVIDER_REQUEST_REJECTED"
                )
                failure_message = (
                    "The model provider is rate-limiting requests. Please wait briefly and retry."
                    if status == 429
                    else "The model provider is temporarily unavailable. Please retry."
                    if status >= 500
                    else "The model provider rejected the request. Check the server's provider configuration."
                )
            run.status, run.error = ("cancelled" if cancelled else "failed"), type(exc).__name__
            run.answer, run.sources, run.citations = (
                failure_message,
                [],
                [],
            )
            data = {
                "code": code,
                "message": failure_message,
                "correlation_id": uid,
                "retryable": True,
                "finished_at": now(),
            }
            await self.store.finish(
                run, "cancelled" if cancelled else "error", data, query.principal
            )
            raise
        finally:
            self._queries.pop(uid, None)
            self._budgets.pop(uid, None)
            self._guards.pop(uid, None)
            self._supported.pop(uid, None)
            self._limitations.pop(uid, None)
            self._document_context.pop(uid, None)
            self._outcomes.pop(uid, None)
            self.runner.locks.pop(uid, None)
            self.runner.counts.pop(uid, None)

    async def events(
        self, run_id: str, principal: Principal, last_id: int = 0
    ) -> AsyncIterator[Event]:
        for event in await self.store.events(run_id, principal, last_id):
            yield event

    async def cancel(self, run_id: str, principal: Principal) -> None:
        run = await self.store.get_run(run_id, principal)
        if run.status not in {"completed", "failed", "cancelled"}:
            run.status, run.answer, run.sources, run.citations = (
                "cancelled",
                "Response cancelled.",
                [],
                [],
            )
            await self.store.finish(
                run,
                "cancelled",
                {
                    "code": "CANCELLED",
                    "message": "Response cancelled.",
                    "correlation_id": run.id,
                    "retryable": True,
                    "finished_at": now(),
                },
                principal,
            )
