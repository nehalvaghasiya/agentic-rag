"""Citation/source preview resolved via current server-side permissions."""

from dataclasses import asdict

from fastapi import APIRouter, Depends

from agentic_rag.api.deps import get_principal, get_runtime
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.models.principal import Principal

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.get("/{evidence_id}")
async def source(
    evidence_id: str,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, object]:
    found = await runtime.search.get([evidence_id], principal)
    if not found:
        raise PermissionError("Source unavailable")
    return asdict(found[0])
