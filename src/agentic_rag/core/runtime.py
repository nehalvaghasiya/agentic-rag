"""Runtime assembly: a single place for shared clients, index and agent services."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentic_rag.agent.service import AgentService
from agentic_rag.core.config import Settings
from agentic_rag.data.fake import FakeStore
from agentic_rag.data.memory import MemoryRepository
from agentic_rag.data.postgres import PostgresRepository
from agentic_rag.data.repository import Repository
from agentic_rag.knowledge.service import KnowledgeService
from agentic_rag.knowledge.worker import IngestWorker
from agentic_rag.memory.private import PrivateMemory
from agentic_rag.ops.metrics import Metrics
from agentic_rag.ops.trace import TraceService
from agentic_rag.providers.fake import FakeChat
from agentic_rag.providers.hash import HashEmbed
from agentic_rag.providers.open_embed import OpenAIEmbed
from agentic_rag.providers.openai import OpenAIChat
from agentic_rag.search.service import SearchService
from agentic_rag.security.auth import AuthService
from agentic_rag.skills.registry import SkillRegistry
from agentic_rag.tools.approval import ApprovalService
from agentic_rag.tools.calculate import CalculateTool
from agentic_rag.tools.listing import ListDocsTool
from agentic_rag.tools.lookup import LookupTool
from agentic_rag.tools.registry import ToolRegistry
from agentic_rag.tools.search import SearchTool
from agentic_rag.tools.sql import SqlTool
from agentic_rag.tools.time import TimeTool


class RuntimeFactory:
    """Own all live dependencies for one API/worker process."""

    def __init__(self, settings: Settings, fixture_root: Path | None = None) -> None:
        settings.validate_runtime()
        self.settings = settings
        self.metrics = Metrics()
        self.trace = TraceService()
        self.store: Any
        self.repo: Repository
        if settings.store == "fake":
            fake = FakeStore()
            self.store = fake
            self.repo = MemoryRepository(fake)
        else:
            pg = PostgresRepository(settings.database_url or "")
            self.store = pg
            self.repo = pg
        self.checkpoint_context: Any = None
        embedding_provider = settings.embedding_provider or settings.provider
        self.embed = (
            HashEmbed()
            if embedding_provider == "fake"
            else OpenAIEmbed(
                settings.embedding_model,
                settings.embedding_api_key
                if settings.embedding_api_key is not None
                else settings.api_key or "",
                settings.embedding_base_url or settings.base_url,
            )
        )
        self.chat = (
            FakeChat()
            if settings.provider == "fake"
            else OpenAIChat(settings.model, settings.api_key or "", settings.base_url)
        )
        self.search = SearchService(self.repo, self.embed)
        self.knowledge = KnowledgeService(self.repo)
        self.worker = IngestWorker(
            self.repo,
            self.embed,
            metrics=self.metrics,
            trace=self.trace,
            tenant_id=settings.worker_tenant_id,
        )
        self.auth = AuthService(
            settings.jwt_secret,
            settings.jwt_issuer,
            settings.jwt_audience,
            demo=settings.environment == "demo",
        )
        self.registry = ToolRegistry()
        for tool in (
            SearchTool(self.search),
            LookupTool(self.search),
            ListDocsTool(self.repo),
            CalculateTool(),
            TimeTool(),
        ):
            self.registry.register(tool)
        root = fixture_root or (Path(__file__).resolve().parents[1] / "resources" / "demo")
        dataset = (
            Path(settings.sql_dataset_path)
            if settings.sql_dataset_path
            else root / "invoices.csv"
            if settings.provider == "fake"
            else None
        )
        if dataset is not None:
            if not dataset.is_file() or dataset.suffix.lower() != ".csv":
                raise ValueError("Configure SQL_DATASET_PATH as an existing approved CSV dataset")
            self.registry.register(SqlTool(dataset))
        self.approvals = ApprovalService(self.repo)
        skills_root = Path(__file__).resolve().parents[1] / "resources" / "skills"
        self.skills = SkillRegistry(skills_root)
        self.skills.load()
        self.agent = AgentService(
            self.repo,
            self.search,
            self.chat,
            self.registry,
            skills=self.skills,
            strict_graph=settings.environment == "production",
            metrics=self.metrics,
            trace=self.trace,
            streaming=settings.streaming,
        )
        self.memory = PrivateMemory(self.repo)
        self.sessions = self.agent.sessions
        self.tasks: dict[str, Any] = {}

    async def open(self) -> None:
        await self.repo.open()
        if self.settings.store == "postgres":
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg.conninfo import make_conninfo

            self.checkpoint_context = AsyncPostgresSaver.from_conn_string(
                make_conninfo(
                    self.settings.database_url or "",
                    options="-c search_path=rag_checkpoints,public",
                )
            )
            saver = await self.checkpoint_context.__aenter__()
            self.agent.configure_graph(saver)

    async def close(self) -> None:
        if self.checkpoint_context:
            await self.checkpoint_context.__aexit__(None, None, None)
        await self.repo.close()
        if hasattr(self.embed, "close"):
            await self.embed.close()
        if hasattr(self.chat, "close"):
            await self.chat.close()
