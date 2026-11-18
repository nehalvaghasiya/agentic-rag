"""Sensitive token and credential redaction for diagnostics."""

import re


class Redactor:
    def text(self, text: str) -> str:
        text = re.sub(r"(?i)(bearer\s+)[a-z0-9._-]+", r"\1[REDACTED]", text)
        text = re.sub(r"(?i)(api[_-]?key\s*[:=]\s*)\S+", r"\1[REDACTED]", text)
        return text

    def structured(self, value: dict[str, object]) -> dict[str, object]:
        return {
            key: "[REDACTED]"
            if any(s in key.lower() for s in ("secret", "token", "password", "api_key"))
            else item
            for key, item in value.items()
        }
