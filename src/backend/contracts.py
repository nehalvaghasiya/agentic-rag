"""OpenAPI additions for the SSE execution contract."""

from typing import Any

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder

from backend.models import EXECUTION_EVENT_ADAPTER

API_VERSION = "2.0.0"
EVENT_SCHEMA_REF = {"$ref": "#/components/schemas/ExecutionEvent"}


def install_event_schema(app: FastAPI) -> None:
    """Extend the same cached document served by FastAPI and exported by tooling."""
    original_openapi = app.openapi

    def openapi() -> dict[str, Any]:
        schema = original_openapi()
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        event_schema = jsonable_encoder(
            EXECUTION_EVENT_ADAPTER.json_schema(
                mode="serialization", ref_template="#/components/schemas/{model}"
            ),
            exclude_none=True,
        )
        for name, definition in event_schema.pop("$defs", {}).items():
            if name in components and components[name] != definition:
                raise ValueError(f"Conflicting contract component: {name}")
            components[name] = definition
        components["ExecutionEvent"] = event_schema
        for path in schema["paths"].values():
            for operation in path.values():
                if "text/event-stream" in operation.get("responses", {}).get("200", {}).get(
                    "content", {}
                ):
                    operation["x-event-schema"] = EVENT_SCHEMA_REF.copy()
        return schema

    app.openapi = openapi
