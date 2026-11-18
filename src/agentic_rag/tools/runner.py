"""Bounded, policy-checked tools with durable observations and idempotency receipts."""

import asyncio
import json
import time
from dataclasses import asdict
from uuid import uuid4

from agentic_rag.data.cache import fingerprint
from agentic_rag.data.repository import Repository
from agentic_rag.memory.conversation import now
from agentic_rag.models.budget import Budget
from agentic_rag.models.result import ToolResult
from agentic_rag.ops.metrics import Metrics
from agentic_rag.ops.trace import TraceService
from agentic_rag.security.tools import ToolPolicy
from agentic_rag.tools.base import ToolContext
from agentic_rag.tools.registry import ToolRegistry


class ToolRunner:
    def __init__(
        self,
        registry: ToolRegistry,
        store: Repository,
        policy: ToolPolicy | None = None,
        metrics: Metrics | None = None,
        trace: TraceService | None = None,
    ) -> None:
        self.registry, self.store, self.policy = registry, store, policy or ToolPolicy()
        self.metrics, self.trace = metrics, trace or TraceService()
        self.counts: dict[str, int] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    async def execute(
        self,
        name: str,
        arguments: dict[str, object],
        context: ToolContext,
        budget: Budget,
        *,
        approved: bool = False,
        call_id: str | None = None,
    ) -> ToolResult:
        tool = self.registry.get(name)
        self.policy.authorize(tool.spec, context.principal, approved)
        run = await self.store.get_run(context.run_id, context.principal)
        if run.status in {"cancelled", "failed", "completed"}:
            raise RuntimeError("Run is no longer active")
        cid = call_id or uuid4().hex
        key = f"{context.run_id}:{cid}"
        digest = fingerprint({"name": name, "arguments": arguments})
        async with self.locks.setdefault(context.run_id, asyncio.Lock()):
            old = await self.store.state_get("receipt", key, context.principal)
            if old:
                if old["fingerprint"] != digest:
                    raise PermissionError("Tool call replay mismatch")
                data = old["result"]
                return ToolResult(**{**data, "evidence_ids": tuple(data["evidence_ids"])})
            count = self.counts.get(context.run_id, 0)
            if count >= budget.max_tool_calls:
                raise RuntimeError("Tool budget exhausted")
            schema = tool.spec.parameters
            properties, required = schema.get("properties", {}), schema.get("required", [])
            if not isinstance(properties, dict) or not isinstance(required, list):
                raise ValueError("Invalid tool schema")
            if any(k not in arguments for k in required) or any(
                k not in properties for k in arguments
            ):
                raise ValueError("Tool arguments failed schema validation")
            for key_name, val in arguments.items():
                definition = properties[key_name]
                if not isinstance(definition, dict):
                    raise ValueError("Invalid tool property")
                typ = definition.get("type")
                if typ == "string" and (not isinstance(val, str) or len(val) > 1024):
                    raise ValueError("Invalid tool string argument")
                if typ == "number" and (not isinstance(val, (int, float)) or isinstance(val, bool)):
                    raise ValueError("Invalid tool number argument")
            self.counts[context.run_id] = count + 1
        await self.store.log(
            context.run_id,
            "tool_started",
            {
                "name": name,
                "call_id": cid,
                "parent_id": context.parent_id,
                "arguments": arguments,
                "title": f"Calling {name}",
            },
            context.principal,
        )
        started = time.monotonic()
        try:
            with self.trace.span("rag.tool", {"tool.name": name}):
                result = await asyncio.wait_for(
                    tool.invoke(arguments, context), timeout=min(8.0, budget.max_seconds)
                )
            if len(json.dumps(result.output, default=str)) > 32000:
                result = ToolResult(name, "error", {}, error="OutputLimitExceeded")
        except (TimeoutError, ValueError, PermissionError, RuntimeError) as exc:
            result = ToolResult(name, "error", {}, error=type(exc).__name__)
        elapsed = round((time.monotonic() - started) * 1000, 3)
        result = ToolResult(
            name, result.status, result.output, result.evidence_ids, result.error, elapsed
        )
        observation = {
            "id": cid,
            "tool": name,
            "arguments": arguments,
            "result": asdict(result),
            "observed_at": now(),
            "session_id": run.session_id,
            "fingerprint": digest,
        }
        await self.store.state_put("observation", key, observation, context.principal)
        if result.status == "ok":
            await self.store.state_put("receipt", key, observation, context.principal)
        if self.metrics:
            self.metrics.tools.labels(name, result.status).inc()
        await self.store.audit(
            {"action": "tool", "name": name, "run": context.run_id, "status": result.status},
            context.principal,
        )
        await self.store.log(
            context.run_id,
            "tool_finished",
            {
                "name": name,
                "call_id": cid,
                "parent_id": context.parent_id,
                "status": result.status,
                "duration_ms": elapsed,
                "output": result.output,
                "error": result.error,
                "title": f"{name} {result.status}",
            },
            context.principal,
        )
        return result
