"""Trusted read-only skill documents from a fixed project directory."""

import hashlib
import re
from pathlib import Path

from agentic_rag.models.skill import Skill


class SkillRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._skills: dict[str, Skill] = {}

    def load(self) -> list[Skill]:
        found = []
        for file in sorted(self.root.glob("*.md")):
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,40}", file.stem):
                raise ValueError("Invalid skill name")
            data = file.read_text(encoding="utf-8")
            if len(data) > 8000 or not data.startswith("---\n"):
                raise ValueError("Invalid skill metadata")
            header, _, body = data[4:].partition("\n---\n")
            fields = dict(line.split(":", 1) for line in header.splitlines() if ":" in line)
            if not fields.get("version") or not fields.get("tools"):
                raise ValueError("Skill missing version/tools")
            skill = Skill(
                file.stem,
                fields["version"].strip(),
                tuple(x.strip() for x in fields.get("trigger", "").split(",") if x.strip()),
                tuple(x.strip() for x in fields["tools"].split(",") if x.strip()),
                body.strip(),
                hashlib.sha256(data.encode()).hexdigest(),
            )
            self._skills[skill.name] = skill
            found.append(skill)
        return found

    def get(self, name: str, allowed_tools: set[str]) -> Skill:
        skill = self._skills[name]
        if not set(skill.tools).issubset(allowed_tools):
            raise PermissionError("Skill cannot grant additional tool permissions")
        return skill
