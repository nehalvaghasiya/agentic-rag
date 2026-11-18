"""Skill domain model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    version: str
    trigger: tuple[str, ...]
    tools: tuple[str, ...]
    instructions: str
    checksum: str
