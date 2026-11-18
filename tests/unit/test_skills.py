"""Trusted skill registry cannot expand tool grants."""

from pathlib import Path

import pytest

from agentic_rag.skills.registry import SkillRegistry


def test_skills() -> None:
    root = Path(__file__).resolve().parents[2] / "skills"
    registry = SkillRegistry(root)
    assert len(registry.load()) == 8
    assert registry.get("verify", {"lookup"}).tools == ("lookup",)
    with pytest.raises(PermissionError):
        registry.get("sql", {"search"})
