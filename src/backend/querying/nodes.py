"""RAG workflow nodes.

All graph nodes for the retrieval-augmented generation workflow.
Each node is a pure function that performs one step of the pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.documents import Document

from backend.config import Prompts
from backend.errors import report_failure
from backend.prompts import build_answer_messages, build_task_messages

if TYPE_CHECKING:
    from backend.storage.vector import VectorStore


def rewrite_query(question: str, llm) -> str:
    """Rewrite a question as an optimized search query.

    Args:
        question: Original user question.
        llm: Language model for rewriting (can be None).

    Returns:
        Optimized search query.
    """
    if llm is None:
        return question

    try:
        prompt = build_task_messages(Prompts.QUERY_REWRITE, question)
        response = llm.invoke(prompt)
        result = str(getattr(response, "content", response)).strip()
        return result or question
    except Exception as exc:
        report_failure(exc, operation="query.rewrite", terminal=False)
        return question


def retrieve(query: str, store: VectorStore, k: int = 5) -> list[Document]:
    """Retrieve relevant documents from the vector store.

    Args:
        query: Search query.
        store: Vector store to search.
        k: Number of documents to retrieve.

    Returns:
        List of relevant documents.
    """
    return store.search(query, k=k)


def grade(question: str, docs: list[Document], llm) -> list[Document]:
    """Grade documents for relevance to the question.

    Args:
        question: User question.
        docs: Documents to grade.
        llm: Language model for grading (can be None).

    Returns:
        Filtered list of relevant documents.
    """
    if llm is None or not docs:
        return docs

    relevant = []
    for doc in docs:
        try:
            excerpt = doc.page_content[:1000]
            prompt = build_task_messages(
                Prompts.GRADE, f"Question: {question}\n\nExcerpt: {excerpt}"
            )
            response = llm.invoke(prompt)
            answer = str(getattr(response, "content", response)).strip().lower()

            if answer.startswith("y"):
                relevant.append(doc)
        except Exception as exc:
            report_failure(exc, operation="query.grade", terminal=False)
            # On error, include the document
            relevant.append(doc)

    # Fallback: if nothing is relevant, return top 3
    return relevant if relevant else docs[:3]


def generate(question: str, docs: list[Document], llm) -> str:
    """Generate an answer from the question and documents.

    Args:
        question: User question.
        docs: Context documents.
        llm: Language model for generation.

    Returns:
        Generated answer string.
    """
    if not docs:
        return (
            "I couldn't find relevant information in the knowledge base. "
            "Try rephrasing your question or adding more documents."
        )

    if llm is None:
        # Fallback for no LLM
        snippets = []
        for i, doc in enumerate(docs[:3], 1):
            source = doc.metadata.get("source", "unknown")
            snippets.append(f"[{i}] {source}: {doc.page_content[:200]}...")
        return "Here are the relevant excerpts:\n\n" + "\n\n".join(snippets)

    prompt = build_answer_messages(question, docs)

    response = llm.invoke(prompt)
    return str(getattr(response, "content", response)).strip()


def generate_stream(question: str, docs: list[Document], llm):
    """Generate an answer with streaming.

    Args:
        question: User question.
        docs: Context documents.
        llm: Language model for generation.

    Yields:
        Token strings as they are generated.
    """
    if not docs:
        yield (
            "I couldn't find relevant information in the knowledge base. "
            "Try rephrasing your question or adding more documents."
        )
        return

    if llm is None:
        # Fallback for no LLM
        for i, doc in enumerate(docs[:3], 1):
            source = doc.metadata.get("source", "unknown")
            yield f"[{i}] {source}: {doc.page_content[:200]}...\n\n"
        return

    prompt = build_answer_messages(question, docs)

    for chunk in llm.stream(prompt):
        token = getattr(chunk, "content", None)
        if token:
            yield token


__all__ = ["rewrite_query", "retrieve", "grade", "generate", "generate_stream"]
