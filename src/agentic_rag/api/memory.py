"""Explicit optional personal memory controls, separate from per-chat history."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from agentic_rag.api.deps import get_principal, get_runtime
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.models.principal import Principal

router = APIRouter(prefix="/memory", tags=["Memory"])


class ConsentBody(BaseModel):
    enabled: bool


@router.put("/consent")
async def consent(
    payload: ConsentBody,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, bool]:
    await runtime.memory.consent(principal, payload.enabled)
    return {"enabled": payload.enabled}


@router.get("")
async def memories(
    runtime: RuntimeFactory = Depends(get_runtime), principal: Principal = Depends(get_principal)
) -> list[dict[str, object]]:
    return await runtime.memory.recall(principal)


@router.delete("/{memory_id}", status_code=204)
async def delete(
    memory_id: str,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> None:
    await runtime.memory.forget(principal, memory_id)
