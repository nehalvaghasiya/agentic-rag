"""Chunk IDs stay stable for the same document version and change on update."""

from agentic_rag.knowledge.chunker import Chunker
from agentic_rag.models.document import Document


def test_stable_ids_and_overlap() -> None:
    doc = Document("a", "kb", "tenant", "example.txt", "text/plain")
    chunker = Chunker(size=5, overlap=2)
    sections = [("one two three four five six seven eight nine", 4, "intro")]
    a = chunker.split(doc, sections)
    assert a == chunker.split(doc, sections)
    assert len(a) == 3
    assert a[0].page == 4
    assert "four" in a[0].text and "four" in a[1].text
    doc.version = 2
    assert a[0].id != chunker.split(doc, sections)[0].id
