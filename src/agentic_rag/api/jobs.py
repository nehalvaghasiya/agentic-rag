"""Authorized asynchronous indexing job status."""

from dataclasses import asdict

from fastapi import APIRouter, Depends

from agentic_rag.api.deps import get_principal, get_runtime
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.models.principal import Principal

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, object]:
    return asdict(await runtime.knowledge.status(job_id, principal))
