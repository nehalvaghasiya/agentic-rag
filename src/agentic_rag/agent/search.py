"""An actual specialist worker with public start/finish events."""

from uuid import uuid4

from agentic_rag.models.budget import Budget
from agentic_rag.models.evidence import Evidence
from agentic_rag.models.query import Query
from agentic_rag.search.service import SearchService
from agentic_rag.tools.base import ToolContext
from agentic_rag.tools.runner import ToolRunner


class SearchAgent:
    def __init__(self, runner: ToolRunner, search: SearchService) -> None:
        self.runner, self.search = runner, search

    async def work(
        self, query: Query, run_id: str, goal: str, budget: Budget, parent_id: str | None = None
    ) -> list[Evidence]:
        aid = uuid4().hex
        await self.runner.store.log(
            run_id,
            "agent_started",
            {
                "name": "SearchAgent",
                "activity_id": aid,
                "parent_id": parent_id,
                "description": goal,
                "title": "Search specialist started",
            },
            query.principal,
        )
        status = "failed"
        try:
            context = ToolContext(query.principal, run_id, query.kb_ids, aid)
            result = await self.runner.execute("search", {"query": goal[:1024]}, context, budget)
            status = result.status
            return (
                await self.search.get(list(result.evidence_ids), query.principal)
                if status == "ok"
                else []
            )
        finally:
            await self.runner.store.log(
                run_id,
                "agent_finished",
                {
                    "name": "SearchAgent",
                    "activity_id": aid,
                    "parent_id": parent_id,
                    "status": status,
                    "title": "Search specialist finished",
                },
                query.principal,
            )
