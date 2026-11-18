"""Permission-gated evaluation of the same AgentService as the normal API."""

from pathlib import Path

from fastapi import APIRouter, Depends

from agentic_rag.api.deps import get_principal, get_runtime
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.eval.runner import EvalRunner
from agentic_rag.models.principal import Principal

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.post("/evals")
async def evaluate(
    runtime: RuntimeFactory = Depends(get_runtime), principal: Principal = Depends(get_principal)
) -> dict[str, object]:
    if "evaluator" not in principal.roles and "admin" not in principal.roles:
        raise PermissionError("Evaluator permission required")
    root = Path(__file__).resolve().parents[1] / "resources" / "demo"
    report = await EvalRunner(runtime.agent, runtime.repo).run(
        root / "questions.jsonl", principal=principal
    )
    return {
        "run_id": report.run_id,
        "modes": report.modes,
        "warning": "Offline fake-provider metrics, not a production model benchmark",
    }


@router.get("/tools")
async def tools(
    runtime: RuntimeFactory = Depends(get_runtime), principal: Principal = Depends(get_principal)
) -> list[dict[str, object]]:
    if "admin" not in principal.roles:
        raise PermissionError("Admin permission required")
    return runtime.registry.list()
