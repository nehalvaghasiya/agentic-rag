"""Cheap intent routing first; only ambiguous requests need model classification."""

import re

from agentic_rag.knowledge.intent import document_intent
from agentic_rag.models.route import RouteDecision

DOC = re.compile(
    r"\b(policy|refund|handbook|document|uploaded|attached|contract|invoice|revenue|knowledge base|file|report|according to|in the source)\b",
    re.I,
)
GENERAL = re.compile(
    r"\b(python|javascript|decorator|sky|rag|machine learning|recipe|poem|joke|capital of|list and (?:a )?tuple)\b",
    re.I,
)


class Router:
    def route(self, text: str, mode: str = "auto", has_kb: bool | None = None) -> RouteDecision:
        if mode not in {"auto", "direct", "baseline", "advanced", "agentic"}:
            raise ValueError("Unsupported execution mode")
        low = text.casefold().strip()
        if mode != "auto":
            return RouteDecision(mode, "explicit", 1.0, "Selected execution mode")
        if low.startswith("general answer:"):
            return RouteDecision(
                "direct", "general", 1.0, "User clarified that a general answer is wanted"
            )
        if re.fullmatch(
            r"(hi|hello|hey|thanks|thank you|good (morning|evening|afternoon))[!.\s]*", low
        ):
            return RouteDecision(
                "direct", "conversation", 1.0, "Conversational message; no sources needed"
            )
        document = document_intent(text, bool(has_kb))
        if document.referenced and has_kb is False:
            return RouteDecision(
                "direct", "missing_knowledge", 1.0, "Attach the document needed for this request"
            )
        if document.referenced and document.broad:
            return RouteDecision(
                "agentic" if document.complex else "baseline",
                "document_" + document.operation,
                1.0,
                "Analyze the attached document with full source coverage"
                if document.complex
                else "Read the attached document for the requested " + document.operation,
            )
        aggregate = bool(
            re.search(r"\b(revenue|invoices?)\b", low)
            and re.search(r"\b(total|sum|count|average|revenue|how many)\b", low)
        )
        if aggregate or re.search(r"\b(calculate|current time|utc|all documents)\b", low):
            return RouteDecision(
                "agentic",
                "structured" if "invoice" in low or "revenue" in low else "tool",
                0.95,
                "Requires an available read-only tool",
            )
        if re.search(
            r"\b(latest news|today.s weather|stock price|live score|current president|weather (?:today|now))\b",
            low,
        ):
            return RouteDecision(
                "direct", "live_unavailable", 1.0, "Live web research is not configured"
            )
        doc = (document.referenced or bool(DOC.search(low))) and not (
            GENERAL.search(low)
            and not document.referenced
            and not re.search(
                r"\b(attached|uploaded|according to|in (?:the|our) (?:policy|document|file))\b", low
            )
        )
        kb = has_kb if has_kb is not None else doc or bool(re.search(r"20\d\d", low))
        complex_task = bool(
            re.search(
                r"\b(reconcile|multi-hop|research|contradictions?|tradeoffs?|step.by.step plan|design a|design an|architect|migration plan|multiple constraints)\b",
                low,
            )
        ) or (
            (doc or (kb and not GENERAL.search(low)))
            and bool(
                re.search(
                    r"\b(compare|difference|across|both|changed between|exceptions|versus)\b", low
                )
            )
        )
        complex_task = (
            complex_task
            or len(re.findall(r"\b(and then|also determine|taking into account|subject to)\b", low))
            >= 2
        )
        if doc and not kb:
            return RouteDecision(
                "direct",
                "missing_knowledge",
                0.95,
                "Document question needs an attached knowledge base",
            )
        if complex_task:
            return RouteDecision(
                "agentic",
                "general_complex"
                if not kb
                or (GENERAL.search(low) and not doc)
                or (not doc and re.search(r"\b(design|architect|migration plan)\b", low))
                else "multi",
                0.9,
                "Multiple dependencies or evidence reconciliation",
            )
        if doc and kb:
            return RouteDecision(
                "baseline", "lookup", 0.95, "One factual lookup in the selected knowledge base"
            )
        if (
            GENERAL.search(low)
            or not kb
            or re.search(r"\b(my name|remember|write me|translate|how are you)\b", low)
        ):
            return RouteDecision(
                "direct", "general", 0.95, "General question or conversation; no retrieval required"
            )
        return RouteDecision(
            "baseline", "uncertain", 0.45, "Source requirement needs classification"
        )
