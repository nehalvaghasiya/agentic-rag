"""Validated document answers. The model attributes sources; the server renders citations."""

import re
from dataclasses import dataclass

from agentic_rag.models.evidence import Evidence

DOCUMENT_SOURCE_CHARS = 44000
DOCUMENT_PROMPT_RESERVE = 2500


def source_context_chars(evidence: list[Evidence]) -> int:
    """Conservative estimate including the per-passage source label and metadata."""
    return sum(
        len(item.text)
        + max(
            200, len(item.title) + len(item.section or "passage") + len(str(item.page or "-")) + 40
        )
        for item in evidence
    )


class GroundingError(ValueError):
    """A provider result cannot be safely presented as a cited document answer."""

    def __init__(self, message: str, kind: str = "citation") -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class GroundedAnswer:
    text: str
    supported: bool
    reason: str = ""


def render_grounded(data: object, evidence: list[Evidence]) -> GroundedAnswer:
    if not isinstance(data, dict) or data.get("status") not in {
        "answered",
        "insufficient_evidence",
    }:
        raise GroundingError("Missing document answer status")
    if data["status"] == "insufficient_evidence":
        return GroundedAnswer(
            "",
            False,
            str(data.get("reason", "The passages do not contain the requested information"))[:500],
        )
    blocks = data.get("blocks")
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 24:
        raise GroundingError("Missing document answer blocks")
    allowed = {f"S{i}": item.chunk_id for i, item in enumerate(evidence, 1)}
    allowed.update({item.chunk_id: item.chunk_id for item in evidence})
    paragraphs = []
    for block in blocks:
        if not isinstance(block, dict) or not isinstance(block.get("text"), str):
            raise GroundingError("Invalid document answer block")
        text = block["text"].strip()
        refs = block.get("sources")
        if not text or len(text) > 6000 or not isinstance(refs, list) or not refs:
            raise GroundingError("Every answer block needs explicit supporting sources")
        if any(not isinstance(ref, str) or ref not in allowed for ref in refs):
            raise GroundingError("Document answer refers to an unknown source")
        citations = dict.fromkeys(allowed[ref] for ref in refs)

        def inline(match: re.Match[str], block_refs: frozenset[str] = frozenset(citations)) -> str:
            ref = (match[1] or match[2] or match[3]).removeprefix("source:")
            if ref not in allowed or allowed[ref] not in block_refs:
                raise GroundingError(
                    "Inline source reference is not attributed by its answer block"
                )
            return f"[source:{allowed[ref]}]"

        text = re.sub(r"\[(source:[^\]]+|S\d+)\]|【(source:[^】]+|S\d+)】|\((S\d+)\)", inline, text)
        missing = [cid for cid in citations if f"[source:{cid}]" not in text]
        paragraphs.append(
            text + (" " + " ".join(f"[source:{cid}]" for cid in missing) if missing else "")
        )
    return GroundedAnswer("\n\n".join(paragraphs), True)


def render_implementation_plan(
    data: object, evidence: list[Evidence], min_phases: int = 5
) -> GroundedAnswer:
    """A detailed plan needs actionable phases, rather than a source-backed synopsis."""
    if not isinstance(data, dict) or data.get("status") == "insufficient_evidence":
        return render_grounded(data, evidence)
    phases = data.get("blocks")
    if not isinstance(phases, list) or not min_phases <= len(phases) <= 12:
        raise GroundingError(
            f"The implementation plan needs {min_phases}–12 actionable phases", kind="format"
        )
    blocks = []
    for index, phase in enumerate(phases, 1):
        if (
            not isinstance(phase, dict)
            or not isinstance(phase.get("title"), str)
            or not phase["title"].strip()
        ):
            raise GroundingError("Every implementation phase needs a title", kind="format")
        for key in ("actions", "acceptance"):
            values = phase.get(key)
            if (
                not isinstance(values, list)
                or not 1 <= len(values) <= 6
                or any(not isinstance(v, str) or not v.strip() or len(v) > 600 for v in values)
            ):
                raise GroundingError(
                    f"Every implementation phase needs concise {key}", kind="format"
                )
        dependencies = phase.get("depends_on")
        if not isinstance(dependencies, list) or any(
            type(d) is not int or not 1 <= d < index for d in dependencies
        ):
            raise GroundingError(
                "Implementation dependencies must name earlier phase numbers; use [] for the first phase",
                kind="format",
            )
        title = re.sub(r"^\d+[.)]\s*", "", phase["title"].strip())[:160]
        text = f"**{index}. {title}**\nActions:\n" + "\n".join(f"- {v}" for v in phase["actions"])
        text += "\nDepends on: " + (
            ", ".join(f"Phase {d}" for d in dependencies) if dependencies else "None"
        )
        text += "\nAcceptance checks:\n" + "\n".join(f"- {v}" for v in phase["acceptance"])
        blocks.append({"text": text, "sources": phase.get("sources")})
    return render_grounded({**data, "blocks": blocks}, evidence)
