"""Typed calls validate args, enforce roles, budgets and replay receipts."""

import pytest

from agentic_rag.models.budget import Budget
from agentic_rag.models.principal import Principal
from agentic_rag.models.run import Run
from agentic_rag.tools.base import ToolContext


async def test_tool_call_and_budget(runtime, principal) -> None:
    await runtime.repo.begin_run(
        Run("run123", principal.tenant_id, principal.user_id), None, "test", principal
    )
    context = ToolContext(principal, "run123", ("demo",))
    result = await runtime.agent.runner.execute(
        "calculate",
        {"a": 2, "b": 3, "operation": "multiply"},
        context,
        Budget(max_tool_calls=1),
        call_id="same",
    )
    assert result.output["result"] == 6
    replay = await runtime.agent.runner.execute(
        "calculate",
        {"a": 2, "b": 3, "operation": "multiply"},
        context,
        Budget(max_tool_calls=1),
        call_id="same",
    )
    assert replay.output == result.output
    with pytest.raises(RuntimeError):
        await runtime.agent.runner.execute("time", {}, context, Budget(max_tool_calls=1))


async def test_invalid_tool_args_and_roles(runtime, principal) -> None:
    await runtime.repo.begin_run(
        Run("bad", principal.tenant_id, principal.user_id), None, "test", principal
    )
    context = ToolContext(Principal("u", "demo-tenant"), "another", ("demo",))
    with pytest.raises(PermissionError):
        await runtime.agent.runner.execute("sql", {"operation": "total"}, context, Budget())
    with pytest.raises(ValueError):
        await runtime.agent.runner.execute(
            "calculate",
            {"operation": "multiply"},
            ToolContext(principal, "bad", ("demo",)),
            Budget(),
        )
