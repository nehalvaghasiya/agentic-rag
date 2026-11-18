"""Safe bounded document text extraction with section/page provenance."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import PurePath

from agentic_rag.models.upload import Upload


class ParserRegistry:
    """Extracts bounded text from common document formats without arbitrary execution."""

    MAX_BYTES = 8 * 1024 * 1024
    MAX_CHARS = 2_000_000
    ALLOWED = {".txt", ".md", ".csv", ".json", ".html", ".htm", ".pdf", ".docx"}

    def supports(self, filename: str) -> bool:
        return PurePath(filename).suffix.lower() in self.ALLOWED

    def parse(self, upload: Upload) -> list[tuple[str, int | None, str | None]]:
        filename = upload.filename
        if (
            not filename
            or len(filename) > 200
            or ".." in filename
            or "/" in filename
            or "\\" in filename
            or filename.startswith(".")
        ):
            raise ValueError("Unsafe filename")
        if not self.supports(filename):
            raise ValueError("Unsupported document format")
        if not upload.content or len(upload.content) > self.MAX_BYTES:
            raise ValueError("Invalid document size")

        suffix = PurePath(filename).suffix.lower()
        content = upload.content
        sections: list[tuple[str, int | None, str | None]]
        if suffix == ".pdf":
            if not content.startswith(b"%PDF"):
                raise ValueError("Invalid PDF signature")
            from pypdf import PdfReader

            pdf = PdfReader(io.BytesIO(content), strict=True)
            if len(pdf.pages) > 200:
                raise ValueError("Too many pages")
            sections = [
                (page.extract_text() or "", i + 1, None) for i, page in enumerate(pdf.pages)
            ]
        elif suffix == ".docx":
            if not content.startswith(b"PK"):
                raise ValueError("Invalid DOCX signature")
            from docx import Document

            doc = Document(io.BytesIO(content))
            sections = [(p.text, None, None) for p in doc.paragraphs if p.text.strip()]
            sections.extend(
                (" | ".join(cell.text for cell in row.cells), None, "table")
                for table in doc.tables
                for row in table.rows
            )
        else:
            text = content.decode("utf-8-sig", errors="strict")
            if suffix == ".json":
                text = json.dumps(json.loads(text), ensure_ascii=False)
            elif suffix == ".csv":
                text = "\n".join(" | ".join(r) for r in csv.reader(io.StringIO(text)))
            elif suffix in {".html", ".htm"}:
                from html.parser import HTMLParser

                class Extractor(HTMLParser):
                    def __init__(self) -> None:
                        super().__init__()
                        self.text: list[str] = []
                        self.skip = 0

                    def handle_starttag(
                        self, tag: str, attrs: list[tuple[str, str | None]]
                    ) -> None:
                        if tag in {"script", "style"}:
                            self.skip += 1

                    def handle_endtag(self, tag: str) -> None:
                        if tag in {"script", "style"} and self.skip:
                            self.skip -= 1

                    def handle_data(self, data: str) -> None:
                        if not self.skip:
                            self.text.append(data)

                extractor = Extractor()
                extractor.feed(text)
                text = " ".join(extractor.text)
            if suffix == ".md":
                sections = []
                title = None
                lines: list[str] = []
                fenced = False
                for line in text.splitlines():
                    if re.match(r"^\s*(?:```|~~~)", line):
                        fenced = not fenced
                    heading = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line) if not fenced else None
                    if heading:
                        if lines:
                            sections.append(("\n".join(lines), None, title))
                        lines, title = [line], heading[1]
                    else:
                        lines.append(line)
                if lines:
                    sections.append(("\n".join(lines), None, title))
            else:
                sections = [(text, None, None)]

        clean: list[tuple[str, int | None, str | None]] = []
        length = 0
        for value, page, name in sections:
            value = re.sub(r"[ \t]+", " ", value).strip()
            if value:
                length += len(value)
                if length > self.MAX_CHARS:
                    raise ValueError("Extracted document too large")
                clean.append((value, page, name))
        if not clean:
            raise ValueError("No extractable text")
        return clean
