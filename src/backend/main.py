"""FastAPI application entry point.

Usage:
    uvicorn backend.main:create_app --factory --host 0.0.0.0 --port 8001 --reload
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import Settings
from backend.routes import router
from backend.services import ServicesFactory, build_services


def create_app(
    settings: Settings | None = None,
    *,
    services_factory: ServicesFactory = build_services,
) -> FastAPI:
    """Configure a new application; acquire its services only during startup."""
    app_settings = Settings() if settings is None else settings.model_copy(deep=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with AsyncExitStack() as stack:
            services = await services_factory(app_settings, stack)
            app.state.services = services
            try:
                yield
            finally:
                app.state.services = None

    app = FastAPI(
        title="Agentic RAG API",
        description="RAG-based question answering with streaming support",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.services = None
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")

    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint."""
        return {"message": "Agentic RAG API", "docs": "/docs"}

    return app


__all__ = ["create_app"]
