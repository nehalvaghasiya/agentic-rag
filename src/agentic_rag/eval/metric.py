"""Metric plug-in protocol."""

from typing import Protocol


class Metric(Protocol):
    def score(self, *args: object, **kwargs: object) -> dict[str, float | None]: ...
