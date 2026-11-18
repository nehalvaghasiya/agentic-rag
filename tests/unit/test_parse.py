"""Strict parser format, traversal, empty and signature checks."""

import io

import pytest
from docx import Document
from pypdf import PdfWriter

from agentic_rag.knowledge.parser import ParserRegistry
from agentic_rag.models.upload import Upload


def test_simple_formats() -> None:
    parser = ParserRegistry()
    for name, data in [
        ("doc.md", b"# Title\nContent"),
        ("data.csv", b"a,b\n1,2\n"),
        ("data.json", b'{"a":1}'),
        ("page.html", b"<script>evil</script><p>Safe</p>"),
    ]:
        assert parser.parse(Upload(name, data))
    assert "evil" not in str(parser.parse(Upload("page.html", b"<script>evil</script><p>Safe</p>")))


def test_docx_pdf() -> None:
    doc = Document()
    doc.add_paragraph("A verified document")
    data = io.BytesIO()
    doc.save(data)
    assert "verified" in str(ParserRegistry().parse(Upload("doc.docx", data.getvalue())))
    pdf = PdfWriter()
    pdf.add_blank_page(200, 200)
    data = io.BytesIO()
    pdf.write(data)
    with pytest.raises(ValueError, match="No extractable text"):
        ParserRegistry().parse(Upload("page.pdf", data.getvalue()))


@pytest.mark.parametrize("name", ["../secret.txt", "folder/private.md", ".env", "z.py", "a\\b.txt"])
def test_unsafe_names(name: str) -> None:
    with pytest.raises(ValueError):
        ParserRegistry().parse(Upload(name, b"something"))


def test_bad_pdf_and_over_size() -> None:
    with pytest.raises(ValueError):
        ParserRegistry().parse(Upload("x.pdf", b"not pdf"))
    with pytest.raises(ValueError):
        ParserRegistry().parse(Upload("large.txt", b"X" * (ParserRegistry.MAX_BYTES + 1)))


def test_markdown_preserves_headings_and_ignores_code_block_headings():
    from agentic_rag.knowledge.parser import ParserRegistry
    from agentic_rag.models.upload import Upload

    sections = ParserRegistry().parse(
        Upload(
            "plan.md",
            b"# Plan\nPurpose\n## Rollout\nTwo branches\n```python\n# code comment\n```\n## Final checks\nBackups",
        )
    )
    assert [section[2] for section in sections] == ["Plan", "Rollout", "Final checks"]
    assert "# code comment" in sections[1][0]
