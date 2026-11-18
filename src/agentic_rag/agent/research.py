"""A bounded research specialist; independent evidence goals use at most two workers."""

import asyncio
from uuid import uuid4

from agentic_rag.agent.plan import Planner
from agentic_rag.agent.search import SearchAgent
from agentic_rag.models.budget import Budget
from agentic_rag.models.evidence import Evidence
from agentic_rag.models.query import Query


class ResearchAgent:
    def __init__(self, search: SearchAgent, planner: Planner | None = None) -> None:
        self.search, self.planner = search, planner or Planner()

    async def work(
        self, query: Query, run_id: str, budget: Budget, goals: list[str] | None = None
    ) -> list[Evidence]:
        aid = uuid4().hex
        repo = self.search.runner.store
        await repo.log(
            run_id,
            "agent_started",
            {"name": "ResearchAgent", "activity_id": aid, "title": "Research specialist started"},
            query.principal,
        )
        limiter = asyncio.Semaphore(2)

        async def gather(goal: str) -> list[Evidence]:
            async with limiter:
                return await self.search.work(query, run_id, goal, budget, aid)

        status = "failed"
        try:
            tasks = (goals or list(self.planner.plan(query.text).goals))[
                : min(3, budget.max_tool_calls)
            ]
            results = await asyncio.gather(*(gather(goal) for goal in tasks))
            unique = {e.chunk_id: e for group in results for e in group}
            status = "ok"
            return list(unique.values())
        finally:
            await repo.log(
                run_id,
                "agent_finished",
                {
                    "name": "ResearchAgent",
                    "activity_id": aid,
                    "status": status,
                    "title": "Research specialist finished",
                },
                query.principal,
            )
