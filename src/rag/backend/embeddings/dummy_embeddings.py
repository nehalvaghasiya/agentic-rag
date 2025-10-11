"""
Dummy embeddings for fallback mode when real embedding models are unavailable.

Provides deterministic, document-based embeddings for debugging and graceful degradation.
This allows the system to continue functioning when API keys are missing or services
are unreachable.
"""

import hashlib
import random

from loguru import logger


class DummyEmbeddings:
    """
    Dummy embeddings provider for fallback mode.

    This class generates deterministic embeddings based on text content hash,
    allowing the system to continue functioning when real embedding models are
    unavailable. The embeddings are reproducible (same text = same embedding)
    and have reasonable properties for similarity search.

    Key features:
    1. Deterministic - same input always produces same embedding
    2. Content-aware - embedding is based on actual text hash
    3. Configurable dimensions to match real embeddings
    4. Supports both sync and async interfaces

    This is useful for:
    - Development/debugging without API keys
    - Graceful degradation when API is down
    - Testing the RAG pipeline end-to-end
    - Demonstrating the system without real models

    Args:
        dimensions: Embedding vector dimensions (default 1536 for OpenAI compatibility).

    Example:
        >>> embeddings = DummyEmbeddings(dimensions=1536)
        >>> vectors = embeddings.embed_documents(["Hello", "World"])
        >>> query_vec = embeddings.embed_query("Hello")
    """

    def __init__(self, dimensions: int = 1536):
        """
        Initialize dummy embeddings with specified dimensions.

        Args:
            dimensions: Number of dimensions for embedding vectors.
        """
        self.dimensions = dimensions
        logger.warning(
            f"Using DUMMY embeddings with {dimensions} dimensions. "
            "This is for debugging/fallback only. Real embedding model is unavailable."
        )

    def _text_to_embedding(self, text: str) -> list[float]:
        """
        Generate deterministic embedding from text using hash-based seeding.

        This method creates a reproducible embedding by:
        1. Hashing the text content
        2. Using hash as random seed
        3. Generating random vector with that seed
        4. Normalizing to unit length

        Args:
            text: Input text to embed.

        Returns:
            Normalized embedding vector.
        """
        # Use text hash as seed for reproducibility
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        seed = int(text_hash[:16], 16)  # Use first 16 hex chars as seed

        # Generate deterministic random vector
        rng = random.Random(seed)
        vector = [rng.gauss(0, 1) for _ in range(self.dimensions)]

        # Normalize to unit length (common for embeddings)
        magnitude = sum(x**2 for x in vector) ** 0.5
        normalized = [x / magnitude for x in vector]

        return normalized

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Embed multiple documents.

        Args:
            texts: List of documents to embed.

        Returns:
            List of embedding vectors.
        """
        logger.debug(f"Generating dummy embeddings for {len(texts)} documents")
        embeddings = [self._text_to_embedding(text) for text in texts]
        logger.debug(f"Generated {len(embeddings)} dummy embeddings")
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        """
        Embed a single query.

        Args:
            text: Query text to embed.

        Returns:
            Embedding vector.
        """
        logger.debug(f"Generating dummy embedding for query: {text[:50]}...")
        return self._text_to_embedding(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """
        Async version of embed_documents for compatibility.

        Args:
            texts: List of documents to embed.

        Returns:
            List of embedding vectors.
        """
        # Dummy embeddings are CPU-bound and fast, no need for real async
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> list[float]:
        """
        Async version of embed_query for compatibility.

        Args:
            text: Query text to embed.

        Returns:
            Embedding vector.
        """
        # Dummy embeddings are CPU-bound and fast, no need for real async
        return self.embed_query(text)
