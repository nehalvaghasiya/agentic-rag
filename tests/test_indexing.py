"""Document loading and chunk-boundary regressions."""

from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.documents import Document

from backend.indexing.chunker import chunk_documents
from backend.indexing.loader import load_file
from tests.support import make_pdf


def test_text_loader_decodes_content_and_sets_source(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"

    docs = load_file(path, "café".encode())

    assert len(docs) == 1
    assert docs[0].page_content == "café"
    assert docs[0].metadata == {"source": str(path)}
    assert not path.exists()


def test_text_loader_replaces_invalid_utf8(tmp_path: Path) -> None:
    docs = load_file(tmp_path / "broken.md", b"valid\xfftail")

    assert docs[0].page_content == "valid\ufffdtail"


def test_pdf_loader_uses_local_bytes_and_preserves_page_metadata(tmp_path: Path) -> None:
    path = tmp_path / "fixture.pdf"

    docs = load_file(path, make_pdf("Local PDF fixture"))

    assert path.exists()
    assert len(docs) == 1
    assert "Local PDF fixture" in docs[0].page_content
    assert docs[0].metadata["source"] == str(path)
    assert docs[0].metadata["page"] == 0


@pytest.mark.parametrize(
    ("text", "chunk_size", "chunk_overlap", "expected"),
    [
        ("short", 10, 2, ["short"]),
        ("abcdefgh", 8, 2, ["abcdefgh"]),
        ("abcdefghij", 6, 2, ["abcdef", "efghij"]),
    ],
)
def test_chunk_boundaries(
    text: str, chunk_size: int, chunk_overlap: int, expected: list[str]
) -> None:
    chunks = chunk_documents(
        [Document(page_content=text)],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    assert [chunk.page_content for chunk in chunks] == expected


def test_chunker_stops_after_first_chunk_reaches_overlapping_tail() -> None:
    chunks = chunk_documents(
        [Document(page_content="abcdefghij")],
        chunk_size=8,
        chunk_overlap=6,
    )

    assert [chunk.page_content for chunk in chunks] == ["abcdefgh", "cdefghij"]


def test_chunker_preserves_metadata_and_restarts_indices_per_document() -> None:
    docs = [
        Document(page_content="abcdef", metadata={"source": "one.txt", "page": 0}),
        Document(page_content="uvwxyz", metadata={"source": "two.txt", "page": 4}),
    ]

    chunks = chunk_documents(docs, chunk_size=4, chunk_overlap=1)

    assert [chunk.metadata["chunk_index"] for chunk in chunks] == [0, 1, 0, 1]
    assert [chunk.metadata["source"] for chunk in chunks] == [
        "one.txt",
        "one.txt",
        "two.txt",
        "two.txt",
    ]
    assert docs[0].metadata == {"source": "one.txt", "page": 0}


def test_chunker_skips_empty_documents() -> None:
    chunks = chunk_documents(
        [Document(page_content=""), Document(page_content=" \n\t ")],
        chunk_size=4,
        chunk_overlap=1,
    )

    assert chunks == []


@pytest.mark.parametrize(
    ("chunk_size", "chunk_overlap", "message"),
    [
        (0, 0, "chunk_size must be positive"),
        (-1, 0, "chunk_size must be positive"),
        (4, -1, "chunk_overlap must be non-negative"),
        (4, 4, "chunk_overlap must be less than chunk_size"),
        (4, 5, "chunk_overlap must be less than chunk_size"),
    ],
)
def test_chunker_rejects_invalid_boundaries(
    chunk_size: int, chunk_overlap: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        chunk_documents(
            [Document(page_content="content")],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
