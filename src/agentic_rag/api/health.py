"""Readiness explicitly differentiates an ephemeral demo from production."""

from fastapi import APIRouter, Depends

from agentic_rag.api.deps import get_runtime
from agentic_rag.core.runtime import RuntimeFactory

router = APIRouter()


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(runtime: RuntimeFactory = Depends(get_runtime)) -> dict[str, object]:
    return {
        "status": "ready",
        "store": runtime.settings.store,
        "provider": runtime.settings.provider,
        "ephemeral": runtime.settings.store == "fake",
    }
