"""In-memory vector store with cosine similarity.

A simple, efficient vector store implementation using NumPy.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from langchain_core.documents import Document

if TYPE_CHECKING:
    from backend.llm import Embedder


class VectorStore:
    """In-memory vector store with cosine similarity search.

    Stores documents and their embeddings, supporting efficient
    similarity search for retrieval.
    """

    def __init__(self, embedder: Embedder):
        """Initialize the vector store.

        Args:
            embedder: Embedder instance for creating vectors.
        """
        self._embedder = embedder
        self._docs: list[Document] = []
        self._vectors: np.ndarray | None = None

    def add(self, docs: list[Document]) -> None:
        """Add documents to the store.

        Args:
            docs: Documents to add and embed.
        """
        if not docs:
            return

        texts = [d.page_content for d in docs]
        vecs = np.array(self._embedder.embed_documents(texts), dtype=np.float32)

        self._docs.extend(docs)

        if self._vectors is None:
            self._vectors = vecs
        else:
            self._vectors = np.vstack([self._vectors, vecs])

    def search(self, query: str, k: int = 5) -> list[Document]:
        """Search for similar documents.

        Args:
            query: Query text.
            k: Number of results to return.

        Returns:
            List of most similar documents with similarity scores in metadata.
        """
        if not self._docs or self._vectors is None:
            return []

        # Embed query
        q = np.array(self._embedder.embed_query(query), dtype=np.float32)

        # Cosine similarity
        norms = np.linalg.norm(self._vectors, axis=1) * np.linalg.norm(q)
        scores = self._vectors @ q / (norms + 1e-9)

        # Get top-k indices
        top_idx = np.argsort(scores)[::-1][:k]

        # Return documents with similarity score added to metadata
        results = []
        for i in top_idx:
            doc = self._docs[i]
            # Create a new document with score in metadata
            doc_with_score = Document(
                page_content=doc.page_content,
                metadata={**doc.metadata, "similarity_score": float(scores[i])},
            )
            results.append(doc_with_score)

        return results

    @property
    def count(self) -> int:
        """Return the number of documents in the store."""
        return len(self._docs)

    def save(self, path: Path) -> None:
        """Save the vector store to disk.

        Args:
            path: Path to save the pickle file.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "docs": self._docs,
                    "vectors": self._vectors,
                },
                f,
            )

    @classmethod
    def load(cls, path: Path, embedder: Embedder) -> VectorStore:
        """Load a vector store from disk.

        Args:
            path: Path to the pickle file.
            embedder: Embedder instance (must match original).

        Returns:
            Loaded VectorStore instance.
        """
        store = cls(embedder)

        if path.exists():
            with open(path, "rb") as f:
                data = pickle.load(f)
                store._docs = data.get("docs", [])
                store._vectors = data.get("vectors")

        return store


__all__ = ["VectorStore"]
