"""Document chunking.

Split documents into smaller, overlapping chunks for better retrieval.
"""

from langchain_core.documents import Document


def chunk_documents(
    docs: list[Document],
    chunk_size: int = 800,
    chunk_overlap: int = 120,
) -> list[Document]:
    """Split documents into overlapping chunks.

    Args:
        docs: List of documents to chunk.
        chunk_size: Maximum chunk size in characters.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        List of chunked documents with updated metadata.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be non-negative")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be less than chunk_size")

    chunks: list[Document] = []

    for doc in docs:
        text = doc.page_content
        if not text.strip():
            continue

        step = max(1, chunk_size - chunk_overlap)
        start = 0
        chunk_idx = 0

        while start < len(text):
            end = min(len(text), start + chunk_size)
            chunk_text = text[start:end].strip()

            if chunk_text:
                # Preserve original metadata and add chunk index
                meta = {**doc.metadata, "chunk_index": chunk_idx}
                chunks.append(Document(page_content=chunk_text, metadata=meta))
                chunk_idx += 1

            if end == len(text):
                break

            start += step

    return chunks


__all__ = ["chunk_documents"]
