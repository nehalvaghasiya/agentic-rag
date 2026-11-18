"""Stable model configuration identity without including provider credentials."""

from typing import Any

from agentic_rag.data.cache import fingerprint


def embedding_identity(embed: Any) -> str:
    model = str(getattr(embed, "model", type(embed).__name__))
    signature = fingerprint(
        [
            type(embed).__name__,
            getattr(embed, "url", ""),
            getattr(embed, "dimension", None),
            "embedding-v1",
        ]
    )[:16]
    return f"{model}@{signature}"
