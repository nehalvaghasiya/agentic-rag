"""Embedding implementations.

Provides different embedders for converting text to vectors.
"""

import hashlib

import numpy as np


class HashEmbedder:
    """Deterministic hash-based embedder for testing.

    Uses SHA-256 hashing to create reproducible embeddings without
    requiring model downloads. Useful for testing and development.
    """

    def __init__(self, dims: int = 128):
        """Initialize the hash embedder.

        Args:
            dims: Embedding dimension size.
        """
        self._dims = dims

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        return [self._hash(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query.

        Args:
            text: Query text to embed.

        Returns:
            Embedding vector.
        """
        return self._hash(text)

    def _hash(self, text: str) -> list[float]:
        """Convert text to embedding via hashing.

        Args:
            text: Text to hash.

        Returns:
            Normalized embedding vector.
        """
        h = hashlib.sha256(text.encode()).digest()
        # Repeat hash to fill dimensions
        repeats = (self._dims // 32) + 1
        arr = np.frombuffer(h * repeats, dtype=np.uint8)[: self._dims]
        # Normalize to [0, 1]
        return (arr.astype(np.float32) / 255.0).tolist()


class HFEmbedder:
    """HuggingFace sentence-transformers embedder.

    Wraps sentence-transformers models for embedding generation.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        """Initialize the HuggingFace embedder.

        Args:
            model_name: HuggingFace model name or path.
        """
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query.

        Args:
            text: Query text to embed.

        Returns:
            Embedding vector.
        """
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()


__all__ = ["HashEmbedder", "HFEmbedder"]
