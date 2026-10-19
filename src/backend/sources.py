"""Shared citation conversion for JSON and streaming query responses."""

from pathlib import Path

from langchain_core.documents import Document

from backend.models import Source


def build_sources(docs: list[Document]) -> list[Source]:
    """Convert retrieved documents into API source objects.

    Args:
        docs: LangChain Document-like objects.

    Returns:
        List of Source objects.
    """
    sources: list[Source] = []
    for doc in docs[:5]:
        source_path = doc.metadata.get("source", "unknown")

        page_number = doc.metadata.get("page_label")
        if page_number is not None:
            try:
                page_number = int(page_number)
            except (ValueError, TypeError):
                page_number = doc.metadata.get("page")
        else:
            raw_page = doc.metadata.get("page")
            page_number = (raw_page + 1) if raw_page is not None else None

        similarity_score = doc.metadata.get("similarity_score")
        score_percent = round(similarity_score * 100, 1) if similarity_score is not None else None

        sources.append(
            Source(
                file_name=Path(source_path).name,
                page=page_number,
                chunk=doc.metadata.get("chunk_index"),
                snippet=str(doc.page_content)[:200],
                score=score_percent,
                metadata=dict(doc.metadata),
            )
        )

    return sources
