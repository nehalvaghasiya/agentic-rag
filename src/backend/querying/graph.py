"""LangGraph workflow definition.

Optional graph-based workflow for complex query processing.
This provides a structured approach with explicit state management.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from langchain_core.documents import Document
from langgraph.graph import END, StateGraph

from backend.querying.nodes import generate, grade, retrieve, rewrite_query

if TYPE_CHECKING:
    from backend.config import Settings
    from backend.storage.vector import VectorStore


class QueryState(TypedDict):
    """State for the query workflow."""

    question: str
    query: str
    documents: list[Document]
    answer: str
    retry_count: int


def build_graph(store: VectorStore, llm, settings: Settings):
    """Build the query workflow graph.

    Args:
        store: Vector store for retrieval.
        llm: Language model for generation.
        settings: Application settings.

    Returns:
        Compiled LangGraph workflow.
    """
    graph = StateGraph(QueryState)

    # Define nodes
    def rewrite_node(state: QueryState) -> QueryState:
        query = rewrite_query(state["question"], llm)
        return {**state, "query": query}

    def retrieve_node(state: QueryState) -> QueryState:
        docs = retrieve(state["query"], store, settings.top_k)
        return {**state, "documents": docs}

    def grade_node(state: QueryState) -> QueryState:
        docs = grade(state["question"], state["documents"], llm)
        return {**state, "documents": docs}

    def generate_node(state: QueryState) -> QueryState:
        answer = generate(state["question"], state["documents"], llm)
        return {**state, "answer": answer}

    def should_retry(state: QueryState) -> str:
        """Decide whether to retry or generate answer."""
        if not state["documents"] and state["retry_count"] < settings.max_retries:
            return "rewrite"
        return "generate"

    # Add nodes
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("grade", grade_node)
    graph.add_node("generate", generate_node)

    # Define edges
    graph.set_entry_point("rewrite")
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges(
        "grade",
        should_retry,
        {
            "rewrite": "rewrite",
            "generate": "generate",
        },
    )
    graph.add_edge("generate", END)

    return graph.compile()


def run_query(question: str, store: VectorStore, llm, settings: Settings) -> dict:
    """Run a query through the graph.

    Args:
        question: User question.
        store: Vector store.
        llm: Language model.
        settings: Application settings.

    Returns:
        Final state with answer.
    """
    graph = build_graph(store, llm, settings)

    initial_state: QueryState = {
        "question": question,
        "query": "",
        "documents": [],
        "answer": "",
        "retry_count": 0,
    }

    return graph.invoke(initial_state)


__all__ = ["QueryState", "build_graph", "run_query"]
