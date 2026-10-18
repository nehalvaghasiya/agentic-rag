"""Controlled public failures and allowlisted, correlated diagnostics."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Annotated, Any, get_args, get_origin
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException
from starlette.requests import ClientDisconnect
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.models import (
    ErrorCode,
    ErrorEnvelope,
    PublicError,
    ValidationCode,
    ValidationIssue,
)


@dataclass(frozen=True)
class ErrorSpec:
    status: int
    retryable: bool
    message: str


CATALOG: dict[ErrorCode, ErrorSpec] = {
    ErrorCode.BAD_REQUEST: ErrorSpec(
        400, False, "The request could not be read. Check its format."
    ),
    ErrorCode.NOT_FOUND: ErrorSpec(404, False, "The requested resource was not found."),
    ErrorCode.METHOD_NOT_ALLOWED: ErrorSpec(
        405, False, "This method is not supported for this endpoint."
    ),
    ErrorCode.CONFLICT: ErrorSpec(
        409,
        False,
        "This request conflicts with the current resource state. Refresh before trying again.",
    ),
    ErrorCode.VALIDATION_ERROR: ErrorSpec(
        422, False, "Some request fields are invalid. Check the field details."
    ),
    ErrorCode.RATE_LIMITED: ErrorSpec(429, True, "Too many requests. Try again later."),
    ErrorCode.QUOTA_EXCEEDED: ErrorSpec(
        429, False, "The provider quota is exhausted. Check billing or quota before trying again."
    ),
    ErrorCode.MODEL_NOT_CONFIGURED: ErrorSpec(
        503, False, "Configure a model API key before trying again."
    ),
    ErrorCode.SERVICE_UNAVAILABLE: ErrorSpec(
        503, True, "The service is temporarily unavailable. Try again later."
    ),
    ErrorCode.PROVIDER_AUTH_ERROR: ErrorSpec(
        502,
        False,
        "The model provider rejected the credentials or access. Check the model settings.",
    ),
    ErrorCode.PROVIDER_REQUEST_ERROR: ErrorSpec(
        502, False, "The model provider rejected this request. Check the model settings."
    ),
    ErrorCode.PROVIDER_UNAVAILABLE: ErrorSpec(
        503, True, "The model provider is temporarily unavailable. Try again later."
    ),
    ErrorCode.PROVIDER_TIMEOUT: ErrorSpec(
        504, True, "The model provider did not respond in time. Try again later."
    ),
    ErrorCode.PROVIDER_ERROR: ErrorSpec(
        502, False, "The model provider could not complete the request."
    ),
    ErrorCode.INTERNAL_ERROR: ErrorSpec(
        500, False, "The request could not be completed because of an internal error."
    ),
    ErrorCode.HTTP_ERROR: ErrorSpec(400, False, "The request could not be completed."),
}

VALIDATION_MESSAGES: dict[ValidationCode, str] = {
    "required": "This field is required.",
    "invalid_type": "This field has an invalid type.",
    "invalid_json": "The request must contain valid JSON.",
    "invalid_value": "This field has an invalid value.",
}

logger = logging.getLogger("backend.errors")
correlation_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)
scope_context: ContextVar[Scope | None] = ContextVar("error_scope", default=None)
stage_context: ContextVar[str] = ContextVar("error_stage", default="request")


def validation_issue(field: str, code: ValidationCode = "invalid_value") -> ValidationIssue:
    """Build a validation issue with controlled explanation text."""
    return ValidationIssue(field=field, code=code, message=VALIDATION_MESSAGES[code])


class ApplicationError(Exception):
    """An explicit catalog selection, with no caller-supplied public message."""

    def __init__(self, code: ErrorCode, *, details: list[ValidationIssue] | None = None):
        super().__init__(code.value)
        self.code = code
        self.details = details[:20] if code == ErrorCode.VALIDATION_ERROR and details else None


@dataclass(frozen=True)
class NormalizedError:
    status: int
    envelope: ErrorEnvelope

    def payload(self) -> dict[str, Any]:
        return self.envelope.model_dump(mode="json", exclude_none=True)


def _field_path(request: Request | None, location: tuple[Any, ...]) -> str:
    """Walk the route's declared schema, never echoing unrecognized input keys."""
    if request is None or not location:
        return "request"
    route = request.scope.get("route")
    source, *parts = location
    if source == "body":
        body_field = getattr(route, "body_field", None)
        annotation = getattr(getattr(body_field, "field_info", None), "annotation", None)
    else:
        dependent = getattr(route, "dependant", None)  # codespell:ignore dependant
        params = getattr(dependent, f"{source}_params", [])
        if len(parts) != 1:
            return "request"
        return next((p.name for p in params if p.alias == parts[0]), "request")
    path = ""
    for part in parts:
        # Optional/annotated fields retain the same declared path.
        while get_origin(annotation) is Annotated or (
            get_args(annotation) and type(None) in get_args(annotation)
        ):
            annotation = next(a for a in get_args(annotation) if a is not type(None))
        if get_origin(annotation) is list and type(part) is int:
            path += f"[{part}]"
            annotation = get_args(annotation)[0]
        elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
            declared = next(
                (
                    (name, field)
                    for name, field in annotation.model_fields.items()
                    if part == name or part == field.alias
                ),
                None,
            )
            if declared is None:
                return "request"
            name, field = declared
            path += ("." if path else "") + name
            annotation = field.annotation
        else:
            return "request"
    return path or "request"


def _validation_details(
    exc: RequestValidationError, request: Request | None
) -> list[ValidationIssue]:
    details = []
    for issue in exc.errors()[:20]:
        kind = issue["type"]
        code: ValidationCode = "invalid_value"
        if kind == "missing":
            code = "required"
        elif kind == "json_invalid":
            code = "invalid_json"
        elif kind.endswith(("_type", "_parsing")):
            code = "invalid_type"
        field = "request" if code == "invalid_json" else _field_path(request, issue["loc"])
        details.append(validation_issue(field, code))
    return details


def _provider_code(exc: Exception) -> ErrorCode | None:
    # Importing the application must not initialize provider clients/resources.
    from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAIError

    if isinstance(exc, APITimeoutError):
        return ErrorCode.PROVIDER_TIMEOUT
    if isinstance(exc, APIConnectionError):
        return ErrorCode.PROVIDER_UNAVAILABLE
    if isinstance(exc, APIStatusError):
        if exc.status_code == 429:
            quota_code = exc.code
            if isinstance(exc.body, dict) and isinstance(exc.body.get("error"), dict):
                quota_code = exc.body["error"].get("code", quota_code)
            return (
                ErrorCode.QUOTA_EXCEEDED
                if quota_code == "insufficient_quota"
                else ErrorCode.RATE_LIMITED
            )
        if exc.status_code in (401, 403):
            return ErrorCode.PROVIDER_AUTH_ERROR
        if exc.status_code >= 500:
            return ErrorCode.PROVIDER_UNAVAILABLE
        if 400 <= exc.status_code < 500:
            return ErrorCode.PROVIDER_REQUEST_ERROR
    return ErrorCode.PROVIDER_ERROR if isinstance(exc, OpenAIError) else None


def normalize_error(
    exc: Exception, *, correlation_id: str | None = None, request: Request | None = None
) -> NormalizedError:
    """Classify without serializing exception text, input, or provider payloads."""
    details = None
    status = None
    if isinstance(exc, ApplicationError):
        code, details = exc.code, exc.details
    elif isinstance(exc, RequestValidationError):
        code, details = ErrorCode.VALIDATION_ERROR, _validation_details(exc, request)
    elif isinstance(exc, HTTPException):
        code = {
            400: ErrorCode.BAD_REQUEST,
            404: ErrorCode.NOT_FOUND,
            405: ErrorCode.METHOD_NOT_ALLOWED,
            409: ErrorCode.CONFLICT,
            422: ErrorCode.VALIDATION_ERROR,
            429: ErrorCode.RATE_LIMITED,
            500: ErrorCode.INTERNAL_ERROR,
            503: ErrorCode.SERVICE_UNAVAILABLE,
        }.get(exc.status_code, ErrorCode.HTTP_ERROR)
        status = exc.status_code
    else:
        code = _provider_code(exc) or ErrorCode.INTERNAL_ERROR
    spec = CATALOG[code]
    return NormalizedError(
        status=status if status is not None else spec.status,
        envelope=ErrorEnvelope(
            error=PublicError(
                code=code,
                message=spec.message,
                retryable=spec.retryable,
                correlation_id=correlation_id or correlation_context.get() or str(uuid4()),
                details=details,
            )
        ),
    )


def report_failure(
    exc: Exception,
    failure: NormalizedError | None = None,
    *,
    operation: str | None = None,
    terminal: bool = True,
) -> NormalizedError:
    """Retain useful stack/category context without arbitrary exception strings."""
    from openai import APIStatusError

    failure = failure or normalize_error(exc)
    scope = scope_context.get() or {}
    record: dict[str, Any] = {
        "event": "request_failed" if terminal else "optional_fallback",
        "correlation_id": failure.envelope.error.correlation_id,
        "route": getattr(scope.get("route"), "path", None),
        "operation": operation or stage_context.get(),
        "code": failure.envelope.error.code.value,
        "exceptions": [],
        "stack": [],
    }
    current: BaseException | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited and len(visited) < 5:
        visited.add(id(current))
        record["exceptions"].append(type(current).__name__)
        if isinstance(current, APIStatusError):
            record["provider_status"] = current.status_code
        tb = current.__traceback__
        while tb is not None and len(record["stack"]) < 20:
            record["stack"].append(
                {
                    "module": tb.tb_frame.f_globals.get("__name__"),
                    "function": tb.tb_frame.f_code.co_name,
                    "line": tb.tb_lineno,
                }
            )
            tb = tb.tb_next
        current = current.__cause__ or current.__context__
    level = logging.ERROR if terminal and failure.status >= 500 else logging.WARNING
    logger.log(level, json.dumps(record))
    return failure


async def _handled_error(request: Request, exc: Exception) -> JSONResponse:
    failure = report_failure(exc, normalize_error(exc, request=request))
    # Only framework method metadata is forwarded, never arbitrary error headers.
    headers = {}
    if isinstance(exc, HTTPException) and exc.status_code == 405 and exc.headers:
        if "Allow" in exc.headers:
            headers["Allow"] = exc.headers["Allow"]
    return JSONResponse(failure.payload(), status_code=failure.status, headers=headers)


class SafeErrorMiddleware:
    """Keep request context alive through streaming and handle pre-header errors."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        correlation_id = str(uuid4())
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        correlation_token = correlation_context.set(correlation_id)
        scope_token = scope_context.set(scope)
        stage_token = stage_context.set("request")
        started = False

        async def correlated_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                MutableHeaders(scope=message)["X-Correlation-ID"] = correlation_id
            await send(message)

        try:
            try:
                await self.app(scope, receive, correlated_send)
            except ClientDisconnect:
                return
            except Exception as exc:
                response = await _handled_error(Request(scope), exc)
                if started:
                    # Generator failures are handled by the SSE boundary. An
                    # unrelated late transport fault cannot replace sent headers.
                    raise RuntimeError("Response interrupted; see correlated diagnostics") from None
                await response(scope, receive, correlated_send)
        finally:
            stage_context.reset(stage_token)
            scope_context.reset(scope_token)
            correlation_context.reset(correlation_token)


def install_error_handling(app: FastAPI) -> None:
    """Install before CORS so even unexpected application failures retain CORS."""
    app.add_middleware(SafeErrorMiddleware)
    app.add_exception_handler(RequestValidationError, _handled_error)
    app.add_exception_handler(HTTPException, _handled_error)
