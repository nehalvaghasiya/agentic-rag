"""Deterministic token-window chunking with stable revision identifiers."""

from __future__ import annotations

import hashlib
import re

from agentic_rag.models.chunk import Chunk
from agentic_rag.models.document import Document


class Chunker:
    """Chunk by whitespace tokens, respecting each parsed section and page."""

    def __init__(self, size: int = 180, overlap: int = 30) -> None:
        if size <= 0 or not 0 <= overlap < size:
            raise ValueError("Invalid chunk size/overlap")
        self.size = size
        self.overlap = overlap

    def split(
        self, doc: Document, sections: list[tuple[str, int | None, str | None]]
    ) -> list[Chunk]:
        chunks: list[Chunk] = []
        for text, page, section in sections:
            words = re.findall(r"\S+", text)
            for start in range(0, len(words), self.size - self.overlap):
                part = " ".join(words[start : start + self.size])
                if not part:
                    break
                ordinal = len(chunks)
                digest = hashlib.sha256(
                    f"{doc.id}:{doc.version}:{ordinal}:v1:{part}".encode()
                ).hexdigest()[:24]
                chunks.append(
                    Chunk(
                        digest,
                        doc.id,
                        doc.kb_id,
                        doc.tenant_id,
                        doc.version,
                        part,
                        ordinal,
                        page,
                        section,
                    )
                )
                if start + self.size >= len(words):
                    break
        return chunks
