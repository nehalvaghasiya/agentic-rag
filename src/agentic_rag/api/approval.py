"""Approval decision API backed by explicit server-side pending requests."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from agentic_rag.api.deps import get_principal, get_runtime
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.models.principal import Principal

router = APIRouter(prefix="/approvals", tags=["Approvals"])


class DecisionBody(BaseModel):
    approved: bool


@router.post("/{approval_id}")
async def decision(
    approval_id: str,
    payload: DecisionBody,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, bool]:
    return {"approved": await runtime.approvals.decide(approval_id, principal, payload.approved)}
