"""Public model settings without exposing credentials or arbitrary endpoints."""

from fastapi import APIRouter, Depends

from agentic_rag.api.deps import get_runtime
from agentic_rag.core.runtime import RuntimeFactory

router = APIRouter(tags=["Capabilities"])


@router.get("/models")
async def models(runtime: RuntimeFactory = Depends(get_runtime)) -> dict[str, object]:
    return runtime.settings.public()


@router.get("/settings/public")
async def settings(runtime: RuntimeFactory = Depends(get_runtime)) -> dict[str, object]:
    return runtime.settings.public()
