"""Strict JSONL dataset validation and immutable case loading."""

import json
from pathlib import Path

from agentic_rag.models.case import EvalCase


class DatasetLoader:
    def load(self, path: Path) -> list[EvalCase]:
        cases = []
        seen = set()
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            raw = json.loads(line)
            if not isinstance(raw, dict) or not raw.get("id") or not raw.get("question"):
                raise ValueError(f"Invalid evaluation case at line {line_no}")
            if raw["id"] in seen:
                raise ValueError(f"Duplicate case ID: {raw['id']}")
            seen.add(raw["id"])
            cases.append(
                EvalCase(
                    id=raw["id"],
                    question=raw["question"],
                    answer=raw.get("answer", ""),
                    relevant_ids=tuple(raw.get("relevant_ids", [])),
                    expected_tools=tuple(raw.get("expected_tools", [])),
                    expected_mode=raw.get("expected_mode"),
                    answerable=bool(raw.get("answerable", True)),
                    category=raw.get("category", "single"),
                    kb_ids=tuple(raw.get("kb_ids", ["demo"])),
                    metadata=raw.get("metadata", {}),
                )
            )
        return cases
