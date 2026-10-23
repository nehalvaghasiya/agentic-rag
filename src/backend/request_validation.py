"""Bound declared JSON bodies before FastAPI reads or decodes them."""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import HTTPException, Request
from fastapi.routing import APIRoute
from starlette.responses import Response
from starlette.types import Message

from backend.request_limits import MAX_JSON_BODY_BYTES


class BoundedJSONRoute(APIRoute):
    """Limit JSON receive bytes without changing GET or multipart handling."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()
        if (
            self.body_field is None
            or getattr(self.body_field.field_info, "media_type", None) != "application/json"
        ):
            return handler

        async def bounded(request: Request) -> Response:
            received = 0
            receive = request.receive

            async def limited_receive() -> Message:
                nonlocal received
                message = await receive()
                if message["type"] == "http.request":
                    received += len(message.get("body", b""))
                    if received > MAX_JSON_BODY_BYTES:
                        raise HTTPException(status_code=413)
                return message

            return await handler(Request(request.scope, receive=limited_receive))

        return bounded
