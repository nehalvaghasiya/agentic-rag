"""
Query endpoints for RAG.

Handles user queries with async generation and streaming support.
"""

from fastapi import APIRouter, HTTPException
from loguru import logger

from rag.backend.schemas import QueryRequest, QueryResponse

router = APIRouter(prefix="/query", tags=["query"])


async def process_query(
    request: QueryRequest,
    rag_pipeline,
) -> QueryResponse:
    """
    Process a RAG query.

    This is fully async because:
    1. Query embedding (API call, 50-200ms)
    2. Vector DB similarity search (I/O-bound, 100-500ms)
    3. LLM generation (API call, 5-30+ seconds)

    Total: 5-30+ seconds of I/O-bound operations.
    Async is critical to serve multiple concurrent users.

    Includes fallback mode warnings when dummy models are active.

    Args:
        request: Query request with user question.
        rag_pipeline: RAG pipeline instance.

    Returns:
        Query response with answer, sources, and warnings.
    """
    try:
        logger.info(f"Processing query: {request.query[:100]}...")

        # Execute RAG pipeline (fully async)
        result = await rag_pipeline.query(request.query)

        # Get warnings from pipeline (fallback mode notifications)
        warnings = rag_pipeline.get_warnings()

        # Format response
        response = QueryResponse(
            answer=result["answer"],
            query=result["query"],
            sources=result.get("sources"),
            warnings=warnings if warnings else None,
        )

        if warnings:
            logger.info(f"Query completed with {len(warnings)} warnings: {warnings}")

        return response

    except Exception as e:
        logger.exception(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# This function will be completed in the main app file
