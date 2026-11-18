"""FastAPI dependency injection and trusted identity extraction."""

from typing import cast

from fastapi import Depends, Header, Request

from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.models.principal import Principal


async def get_runtime(request: Request) -> RuntimeFactory:
    return cast(RuntimeFactory, request.app.state.runtime)


async def get_principal(
    authorization: str | None = Header(default=None), runtime: RuntimeFactory = Depends(get_runtime)
) -> Principal:
    return runtime.auth.authenticate(authorization)
