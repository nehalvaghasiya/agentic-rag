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
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url,
    )


def get_embedder(model_name: str, settings: Settings) -> Embedder:
    """Get an embedder for the given model name.

    Args:
        model_name: Model ID accepted by the configured embedding provider.
        settings: Application settings.

    Returns:
        An embedder instance.
    """
    if settings.mode == "deterministic":
        from backend.indexing.embedder import HashEmbedder

        return HashEmbedder()

    # Explicit provider selection supports arbitrary OpenAI-compatible model IDs.
    # Auto retains the original OpenAI/HuggingFace model-name routing.
    if settings.embedding_provider == "openai" or (
        settings.embedding_provider == "auto" and model_name.startswith("text-embedding-")
    ):
        api_key = settings.embedding_api_key or settings.openai_api_key
        if not api_key:
            from backend.errors import ApplicationError
            from backend.models import ErrorCode

            raise ApplicationError(ErrorCode.MODEL_NOT_CONFIGURED)

        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            api_key=api_key,
            model=model_name,
            base_url=settings.embedding_base_url or settings.openai_base_url,
            # Let the endpoint tokenize its own model, rather than sending OpenAI
            # token IDs to providers using another tokenizer.
            check_embedding_ctx_length=False,
            model_kwargs={"encoding_format": "float"},
        )

    # HuggingFace embeddings (default)
    from backend.indexing.embedder import HFEmbedder

    return HFEmbedder(model_name)


__all__ = ["Embedder", "get_llm", "get_embedder"]
