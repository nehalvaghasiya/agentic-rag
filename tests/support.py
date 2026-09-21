"""Deterministic test doubles shared by the backend regression suite."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContentResponse:
    """Minimal LangChain-like response carrying text content."""

    content: str


class ScriptedLLM:
    """LLM double with queued invoke and stream results plus call recording."""

    def __init__(
        self,
        *,
        invoke: Iterable[str | Exception] = (),
        stream: Iterable[str | Exception] = (),
    ) -> None:
        self._invoke_results = deque(invoke)
        self._stream_results = list(stream)
        self.invoke_calls: list[Any] = []
        self.stream_calls: list[Any] = []

    def invoke(self, prompt: Any) -> ContentResponse:
        self.invoke_calls.append(prompt)
        if not self._invoke_results:
            raise AssertionError("No scripted invoke result remains")
        result = self._invoke_results.popleft()
        if isinstance(result, Exception):
            raise result
        return ContentResponse(result)

    def stream(self, prompt: Any):
        self.stream_calls.append(prompt)
        for result in self._stream_results:
            if isinstance(result, Exception):
                raise result
            yield ContentResponse(result)


class ScriptedEmbedder:
    """Embedding double that maps exact input strings to deterministic vectors."""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(list(texts))
        return [list(self._vectors[text]) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return list(self._vectors[text])


def make_pdf(text: str = "Offline backend PDF") -> bytes:
    """Build a one-page text PDF without a fixture-generation dependency."""

    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 20 100 Td ({escaped}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 240 140] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(pdf)
