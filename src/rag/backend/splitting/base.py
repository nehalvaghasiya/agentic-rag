"""
Base text splitter interface.

Defines the contract for all text splitting strategies, following the
Strategy pattern for interchangeable splitting algorithms.
"""

from abc import ABC, abstractmethod

from langchain_core.documents import Document


class TextSplitter(ABC):
    """
    Abstract base class for text splitters.

    Text splitters chunk documents into smaller pieces for embedding and retrieval.
    Different strategies (recursive, semantic, token-based) can be used based on
    the use case.

    Text splitting is CPU-bound (string operations) and synchronous. No async needed.
    """

    @abstractmethod
    def split_documents(self, documents: list[Document]) -> list[Document]:
        """
        Split documents into chunks.

        This is synchronous because text splitting is CPU-bound:
        - String slicing and manipulation
        - Character counting
        - Regex operations

        No I/O operations, so async would not provide benefits.

        Args:
            documents: List of documents to split.

        Returns:
            List of document chunks.

        Example:
            >>> splitter = RecursiveCharacterSplitter(config)
            >>> chunks = splitter.split_documents(documents)
        """
        pass
