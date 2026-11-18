"""Stable safe errors with correlation IDs and no internal messages."""

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agentic_rag.data.repository import ConflictError, ContentUnavailableError


def install_errors(app: FastAPI) -> None:
    @app.exception_handler(ContentUnavailableError)
    async def unavailable_content(request: Request, error: ContentUnavailableError) -> JSONResponse:
        uid = uuid4().hex
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "CONTENT_UNAVAILABLE",
                    "message": "The original file is unavailable for this document.",
                    "correlation_id": uid,
                    "retryable": False,
                }
            },
            headers={"X-Correlation-ID": uid, "Cache-Control": "private, no-store"},
        )

    @app.exception_handler(ConflictError)
    async def conflict(request: Request, error: ConflictError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "CONFLICT",
                    "message": str(error),
                    "correlation_id": uuid4().hex,
                    "retryable": False,
                }
            },
        )

    @app.exception_handler(PermissionError)
    async def forbidden(request: Request, error: PermissionError) -> JSONResponse:
        uid = uuid4().hex
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "ACCESS_DENIED",
                    "message": "Access denied",
                    "correlation_id": uid,
                    "retryable": False,
                }
            },
            headers={"X-Correlation-ID": uid},
        )

    @app.exception_handler(ValueError)
    async def invalid(request: Request, error: ValueError) -> JSONResponse:
        uid = uuid4().hex
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": str(error)[:160],
                    "correlation_id": uid,
                    "retryable": False,
                }
            },
            headers={"X-Correlation-ID": uid},
        )

    @app.exception_handler(Exception)
    async def broken(request: Request, error: Exception) -> JSONResponse:
        uid = uuid4().hex
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An internal error occurred",
                    "correlation_id": uid,
                    "retryable": True,
                }
            },
            headers={"X-Correlation-ID": uid},
        )
