"""Treat retrieved text as untrusted data; deterministic high-risk pattern flags."""

import re


class InjectionGuard:
    def assess(self, text: str) -> bool:
        patterns = (
            r"ignore (all )?(previous|system) instructions",
            r"reveal (your )?(system prompt|api key)",
            r"send (credentials|secrets|tokens) to",
        )
        return any(re.search(pattern, text, re.I) is not None for pattern in patterns)

    def isolate_untrusted(self, text: str) -> str:
        return (
            "<untrusted_source>\n"
            + text.replace("</untrusted_source>", "")
            + "\n</untrusted_source>"
        )
