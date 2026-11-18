"""Durable explicit approval decisions; no write tools are enabled by chat."""

from uuid import uuid4

from agentic_rag.data.repository import Repository
from agentic_rag.models.principal import Principal


class ApprovalService:
    def __init__(self, store: Repository) -> None:
        self.store = store

    async def request(self, principal: Principal, run_id: str, tool: str) -> str:
        run = await self.store.get_run(run_id, principal)
        uid = uuid4().hex
        await self.store.state_put(
            "approval",
            uid,
            {"run": run_id, "tool": tool, "decision": None, "session_id": run.session_id},
            principal,
        )
        await self.store.log(
            run_id,
            "plan",
            {"approval_id": uid, "tool": tool, "title": "Explicit approval required"},
            principal,
        )
        return uid

    async def decide(self, uid: str, principal: Principal, approved: bool) -> bool:
        request = await self.store.state_get("approval", uid, principal)
        if not request:
            raise PermissionError("Approval unavailable")
        if request["decision"] is not None:
            raise ValueError("Approval already decided")
        request["decision"] = approved
        await self.store.state_put("approval", uid, request, principal)
        return approved
