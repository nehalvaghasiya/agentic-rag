"""FastAPI application entry point.

Usage:
    uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.routes import router

settings = get_settings()

app = FastAPI(
    title="Agentic RAG API",
    description="RAG-based question answering with streaming support",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, prefix="/api")


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Agentic RAG API", "docs": "/docs"}


__all__ = ["app"]
