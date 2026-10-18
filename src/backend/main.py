"""FastAPI application entry point.

Usage:
    uvicorn backend.main:create_app --factory --host 0.0.0.0 --port 8001 --reload
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import Settings, resolve_settings
from backend.errors import CATALOG, install_error_handling
from backend.models import ErrorEnvelope
from backend.routes import router
from backend.services import ServicesFactory, build_services


def create_app(
    settings: Settings | None = None,
    *,
    services_factory: ServicesFactory = build_services,
) -> FastAPI:
    """Configure a new application; acquire its services only during startup."""
    app_settings = resolve_settings(settings)

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
        description=(
            "RAG-based question answering with streaming support. Failures use ErrorEnvelope "
            "with a stable code, safe message, advisory retryability and correlation_id. "
            "X-Correlation-ID identifies every application response. SSE execution failures "
            "use the same envelope in one terminal error event; HTTP 200 only opens the stream."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        responses={
            status: {
                "model": ErrorEnvelope,
                "description": "\n\n".join(
                    f"{code.value}: {spec.message} Retryable: {spec.retryable}."
                    for code, spec in CATALOG.items()
                    if spec.status == status
                ),
                "headers": {"X-Correlation-ID": {"schema": {"type": "string"}}},
            }
            for status in {spec.status for spec in CATALOG.values()}
        },
    )
    app.state.services = None
    install_error_handling(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"],
    )
    app.include_router(router, prefix="/api")

    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint."""
        return {"message": "Agentic RAG API", "docs": "/docs"}

    return app


__all__ = ["create_app"]
