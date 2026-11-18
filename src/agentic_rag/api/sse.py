"""Strict SSE serialization and monotonic replay without synthetic reasoning steps."""

import json
from dataclasses import asdict

from agentic_rag.models.event import Event


def format_event(event: Event) -> str:
    return f"id: {event.id}\nevent: {event.type}\ndata: {json.dumps(asdict(event))}\n\n"


def parse_last_event_id(value: str | None) -> int:
    if value is None or not value.strip():
        return 0
    if not value.isdecimal():
        raise ValueError("Invalid Last-Event-ID")
    return min(int(value), 10_000_000)
