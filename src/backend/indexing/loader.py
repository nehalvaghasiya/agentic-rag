"""Document loading from files.

Supports PDF, TXT, and other text-based file formats.
"""

from pathlib import Path

from langchain_core.documents import Document


def load_file(path: Path, content: bytes) -> list[Document]:
    """Load a file into LangChain documents.

    Args:
        path: File path (used for determining type and storing source).
        content: Raw file content bytes.

    Returns:
        List of Document objects with page_content and metadata.
    """
    suffix = path.suffix.lower()
    source = str(path)

    if suffix == ".pdf":
        return _load_pdf(path, content)

    # Default: treat as text
    text = content.decode("utf-8", errors="replace")
    return [Document(page_content=text, metadata={"source": source})]


def _load_pdf(path: Path, content: bytes) -> list[Document]:
    """Load a PDF file.

    Args:
        path: File path to write PDF temporarily.
        content: PDF content bytes.

    Returns:
        List of Document objects, one per page.
    """
    # Write to disk for PyPDFLoader
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

    from langchain_community.document_loaders import PyPDFLoader

    docs = PyPDFLoader(str(path)).load()

    # Ensure source is set
    for doc in docs:
        doc.metadata["source"] = str(path)

    return docs


__all__ = ["load_file"]
