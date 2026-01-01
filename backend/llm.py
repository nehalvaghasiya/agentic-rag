"""LLM and embedder factory functions.

Central place for creating LLM and embedding model instances.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from backend.config import Settings


@runtime_checkable
class Embedder(Protocol):
    """Protocol for embedding models."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        ...


def get_llm(settings: Settings):
    """Get the chat model based on settings.

    Args:
        settings: Application settings.

    Returns:
        A LangChain chat model, or None if not configured.
    """
    if settings.mode == "deterministic":
        return None

    if not settings.openai_api_key:
        return None

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.openai_model,
        base_url=settings.openai_base_url,
    )


def get_embedder(model_name: str, settings: Settings) -> Embedder:
    """Get an embedder for the given model name.

    Args:
        model_name: Model name (e.g., "text-embedding-3-small" or HuggingFace model).
        settings: Application settings.

    Returns:
        An embedder instance.
    """
    if settings.mode == "deterministic":
        from backend.indexing.embedder import HashEmbedder

        return HashEmbedder()

    # OpenAI embeddings
    if model_name.startswith("text-embedding-"):
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key required for OpenAI embeddings")

        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            api_key=settings.openai_api_key.get_secret_value(),
            model=model_name,
        )

    # HuggingFace embeddings (default)
    from backend.indexing.embedder import HFEmbedder

    return HFEmbedder(model_name)


__all__ = ["Embedder", "get_llm", "get_embedder"]
