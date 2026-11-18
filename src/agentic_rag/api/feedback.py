"""Small review endpoint, scoped to a run the caller owns."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from agentic_rag.api.deps import get_principal, get_runtime
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.models.principal import Principal

router = APIRouter(tags=["Feedback"])


class FeedbackBody(BaseModel):
    rating: int = Field(ge=1, le=5)
    correction: str | None = Field(default=None, max_length=1000)


@router.post("/runs/{run_id}/feedback")
async def feedback(
    run_id: str,
    payload: FeedbackBody,
    runtime: RuntimeFactory = Depends(get_runtime),
    principal: Principal = Depends(get_principal),
) -> dict[str, str]:
    await runtime.repo.get_run(run_id, principal)
    await runtime.repo.audit(
        {
            "action": "feedback",
            "tenant": principal.tenant_id,
            "run": run_id,
            "rating": payload.rating,
        },
        principal,
    )
    return {"status": "recorded"}
