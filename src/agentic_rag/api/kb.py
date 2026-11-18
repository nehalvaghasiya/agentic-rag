"""Knowledge base create/list/delete API, always tenant-scoped."""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from agentic_rag.api.contracts import KnowledgeBaseResponse
from agentic_rag.api.deps import get_principal, get_runtime
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.models.principal import Principal

router = APIRouter(prefix="/kb", tags=["Knowledge"])


class CreateKb(BaseModel):
    name: str = Field(min_length=1, max_length=100)


async def describe_kb(
    kb: dict[str, Any], runtime: RuntimeFactory, principal: Principal
) -> dict[str, Any]:
    return {
        "id": kb["id"],
        "name": kb["name"],
        "embedding_model": runtime.settings.public()["embedding_model"],
        "created_at": str(kb.get("created_at", "")),
        "documents": await runtime.knowledge.list_docs(kb["id"], principal),
        "can_delete": "admin" in principal.roles,
    }


@router.get("", response_model=list[KnowledgeBaseResponse])
async def list_kbs(
    runtime: RuntimeFactory = Depends(get_runtime), principal: Principal = Depends(get_principal)
) -> list[dict[str, str]]:
    return [
        await describe_kb(kb, runtime, principal) for kb in await runtime.repo.list_kbs(principal)
    ]


@router.post("", status_code=201, response_model=KnowledgeBaseResponse)
async def create_kb(
    payload: CreateKb,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, str]:
    return await describe_kb(
        await runtime.knowledge.create_kb(payload.name, principal), runtime, principal
    )


@router.delete("/{kb_id}", status_code=204)
async def delete_kb(
    kb_id: str,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> None:
    await runtime.knowledge.delete_kb(kb_id, principal)


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_kb(
    kb_id: str,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, Any]:
    return await describe_kb(await runtime.repo.check_kb(kb_id, principal), runtime, principal)
