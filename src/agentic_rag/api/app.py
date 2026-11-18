"""Application factory: dependency injection, authorized routers, metrics and lifespan."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from agentic_rag.api import (
    approval,
    docs,
    evals,
    feedback,
    health,
    jobs,
    kb,
    legacy,
    memory,
    models,
    runs,
    sessions,
    sources,
)
from agentic_rag.api.deps import get_principal, get_runtime
from agentic_rag.api.errors import install_errors
from agentic_rag.core.config import Settings
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.models.principal import Principal


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.load()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        runtime = RuntimeFactory(config)
        app.state.runtime = runtime
        try:
            await runtime.open()
            yield
        finally:
            import asyncio

            tasks = list(runtime.tasks.values())
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await runtime.close()

    app = FastAPI(title="Advanced Agentic RAG", version="0.2.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allow_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Last-Event-ID"],
        allow_credentials=False,
    )
    for router in (
        health.router,
        kb.router,
        docs.router,
        jobs.router,
        runs.router,
        sessions.router,
        sources.router,
        approval.router,
        memory.router,
        feedback.router,
        evals.router,
        models.router,
    ):
        app.include_router(router, prefix="/api/v2")
    app.include_router(legacy.router)
    install_errors(app)

    @app.get("/metrics", include_in_schema=False)
    async def metrics(
        runtime: RuntimeFactory = Depends(get_runtime),
        principal: Principal = Depends(get_principal),
    ) -> Response:
        if "admin" not in principal.roles:
            raise PermissionError("Metrics restricted")
        return Response(runtime.metrics.export(), media_type="text/plain; version=0.0.4")

    return app
