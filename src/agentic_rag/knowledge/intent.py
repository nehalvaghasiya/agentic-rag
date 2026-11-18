"""Document references and operations shared by routing and document reading."""

import re
from dataclasses import dataclass

REFERENCE = re.compile(
    r"\b(?:this|that|the attached|the uploaded|attached|uploaded|selected|our)\s+"
    r"(?:plan|documents?|files?|reports?|proposals?|text|knowledge(?:\s+base)?|material|content)\b"
    r"|\b(?:according to|based on (?:it|this|that)|from (?:the|these) documents)\b"
    r"|\b(?:what(?:'s|s| is)|explain|summarize)\s+(?:this|that|it)(?:\s+about)?\b",
    re.I,
)
OVERVIEW = re.compile(
    r"\b(?:summari[sz]e|summary|overview|takeaways?|key (?:points|ideas|themes)|main (?:points|ideas|goals)|"
    r"what(?:'s|s| is)\b.*\babout|explain\s+(?:this|that|it)|what\b.*\b(?:covers?|says?))\b",
    re.I,
)
TRANSFORM = re.compile(
    r"\b(?:create|draft|generate|turn|convert|make|prepare|extract|write|build)\b.*"
    r"\b(?:checklist|plan|roadmap|steps|tasks|table|brief|email|presentation|outline|requirements|implementation)\b",
    re.I,
)
ANALYSIS = re.compile(
    r"\b(?:implementation plan|migration plan|detailed roadmap|compare|reconcile|critique|evaluate|"
    r"contradictions?|tradeoffs?|risks? and|gaps and|prioriti[sz]e)\b",
    re.I,
)


@dataclass(frozen=True)
class DocumentIntent:
    referenced: bool
    operation: str = "lookup"
    complex: bool = False

    @property
    def broad(self) -> bool:
        return self.operation in {"overview", "transform", "analysis"}


def document_intent(text: str, has_kb: bool) -> DocumentIntent:
    explicit = bool(
        REFERENCE.search(text) or re.search(r"\b[\w-]+\.(?:md|txt|pdf|docx|csv|json)\b", text, re.I)
    )
    broad = bool(OVERVIEW.search(text))
    # A bare request to summarize attached material needs no extra intent-model roundtrip.
    referenced = explicit or (
        has_kb and broad and not re.search(r"\b(?:python|javascript|sky|recipe|joke)\b", text, re.I)
    )
    if not referenced:
        return DocumentIntent(False)
    complex_task = bool(ANALYSIS.search(text))
    operation = (
        "analysis"
        if complex_task
        else "overview"
        if broad
        else "transform"
        if TRANSFORM.search(text)
        else "lookup"
    )
    return DocumentIntent(True, operation, complex_task)
