"""
Main FastAPI application.

Initializes all components and sets up routes with async support.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from rag.backend.embeddings.embeddings import create_embeddings
from rag.backend.llm.llm import create_llm
from rag.backend.loaders.factory import LoaderFactory
from rag.backend.preprocessing.cleaner import TextCleaner
from rag.backend.rag_pipeline import RAGPipeline
from rag.backend.routes.query import process_query
from rag.backend.routes.upload import process_upload
from rag.backend.schemas import HealthResponse, QueryRequest, QueryResponse, UploadResponse
from rag.backend.splitting.splitters import create_splitter
from rag.backend.vectorstore.pgvector_store import create_vectorstore
from rag.config import load_config
from rag.logging_config import setup_logging

# Load environment variables from .env file
env_path = Path(__file__).parents[3] / ".env"
load_dotenv(dotenv_path=env_path)

# Global state for dependency injection
app_state = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Initializes all components on startup and cleans up on shutdown.
    """
    # Load configuration
    config = load_config()
    setup_logging(config)

    logger.info("Initializing Agentic RAG application...")

    # Initialize components
    try:
        # Embeddings (supports async for API-based models)
        # Pass fallback config for graceful degradation
        embeddings = create_embeddings(config.embeddings, config.fallback)
        app_state["embeddings"] = embeddings

        # Vector store (async I/O for DB operations)
        vectorstore = create_vectorstore(config.vectorstore.pgvector, embeddings)
        app_state["vectorstore"] = vectorstore

        # LLM (async for API-based models)
        # Pass fallback config for graceful degradation
        llm = create_llm(config.llm, config.fallback)
        app_state["llm"] = llm

        # RAG pipeline (async orchestration)
        # Pass embeddings for fallback detection
        rag_pipeline = RAGPipeline(config, vectorstore, llm, embeddings)
        app_state["rag_pipeline"] = rag_pipeline

        # Document loaders
        loader_factory = LoaderFactory(config)
        app_state["loader_factory"] = loader_factory

        # Preprocessors
        text_cleaner = TextCleaner(config.preprocessing.cleaning)
        app_state["text_cleaner"] = text_cleaner

        # Text splitter
        text_splitter = create_splitter(config.splitting, embeddings)
        app_state["text_splitter"] = text_splitter

        # Store config
        app_state["config"] = config

        logger.info("Application initialized successfully")

    except Exception as e:
        logger.exception(f"Failed to initialize application: {e}")
        raise

    yield

    # Cleanup on shutdown
    logger.info("Shutting down application...")
    app_state.clear()


# Create FastAPI app
config = load_config()
app = FastAPI(
    title=config.app.name,
    version=config.app.version,
    description="Agentic RAG - Retrieval-Augmented Generation with Agents",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_credentials=True,
    allow_methods=config.api.cors_methods,
    allow_headers=config.api.cors_headers,
)


@app.get("/", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns the status of the application and its components.
    """
    return HealthResponse(
        status="healthy",
        version=config.app.version,
        components={
            "embeddings": "initialized" if "embeddings" in app_state else "not ready",
            "vectorstore": "initialized" if "vectorstore" in app_state else "not ready",
            "llm": "initialized" if "llm" in app_state else "not ready",
            "rag_pipeline": "initialized" if "rag_pipeline" in app_state else "not ready",
        },
    )


@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile):
    """
    Upload and process a document.

    This endpoint is fully async to handle I/O-bound operations:
    1. File upload (network I/O)
    2. Document loading (file I/O, OCR, HTTP for websites)
    3. Embedding generation (API calls for cloud-based embeddings)
    4. Vector store writes (database I/O)

    Why async is critical here:
    - Users may upload multiple files concurrently
    - Large files (up to 5MB) take time to read and process
    - Embedding and DB operations are I/O-bound
    - Without async, one upload blocks all other requests

    Example usage:
    ```bash
    curl -X POST "http://localhost:8000/upload" \\
         -F "file=@document.pdf"
    ```
    """
    return await process_upload(
        file=file,
        config=app_state["config"],
        loader_factory=app_state["loader_factory"],
        text_cleaner=app_state["text_cleaner"],
        text_splitter=app_state["text_splitter"],
        vectorstore=app_state["vectorstore"],
        rag_pipeline=app_state["rag_pipeline"],  # For warnings
    )


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Query the RAG system.

    This endpoint is fully async to handle:
    1. Query embedding (API call, 50-200ms)
    2. Vector similarity search (database I/O, 100-500ms)
    3. LLM generation (API call, 5-30+ seconds)

    Why async is critical here:
    - LLM generation can take 5-30+ seconds
    - Multiple users should get responses concurrently
    - Streaming support requires async
    - Without async, one user's query blocks all others

    Example usage:
    ```bash
    curl -X POST "http://localhost:8000/query" \\
         -H "Content-Type: application/json" \\
         -d '{"query": "What is RAG?", "top_k": 5}'
    ```
    """
    return await process_query(
        request=request,
        rag_pipeline=app_state["rag_pipeline"],
    )


if __name__ == "__main__":
    import uvicorn

    # Run with async uvicorn server
    uvicorn.run(
        "rag.backend.app:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.reload,
        workers=config.api.workers if not config.api.reload else 1,
        log_level="info",
    )
