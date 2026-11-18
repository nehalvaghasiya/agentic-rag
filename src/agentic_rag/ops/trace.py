"""OpenTelemetry instrumentation boundary; opt-in exporters configured by operators."""

from collections.abc import Iterator
from contextlib import contextmanager

from opentelemetry import trace


class TraceService:
    def __init__(self) -> None:
        self.tracer = trace.get_tracer("agentic_rag")

    @contextmanager
    def span(self, name: str, attributes: dict[str, str] | None = None) -> Iterator[None]:
        with self.tracer.start_as_current_span(name, attributes=attributes or {}):
            yield
