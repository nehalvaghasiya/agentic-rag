"""
Base preprocessor interface.

Defines the contract for all text preprocessing steps, following the
Strategy pattern for interchangeable preprocessing strategies.
"""

from abc import ABC, abstractmethod

from langchain_core.documents import Document


class Preprocessor(ABC):
    """
    Abstract base class for text preprocessors.

    Each preprocessor implements a single transformation step on documents.
    Preprocessors can be chained using the Decorator pattern for complex
    preprocessing pipelines.

    Preprocessors are typically CPU-bound (regex, string operations) and
    synchronous. Only use async if the preprocessor makes I/O calls (e.g.,
    calling an external summarization API).
    """

    @abstractmethod
    def process(self, documents: list[Document]) -> list[Document]:
        """
        Process a list of documents.

        This is synchronous because most text preprocessing is CPU-bound:
        - Regex operations for cleaning
        - String manipulation
        - Text normalization

        Only use async preprocessors if you're making I/O calls (e.g., API
        calls for summarization or translation).

        Args:
            documents: List of documents to process.

        Returns:
            List of processed documents.

        Example:
            >>> preprocessor = TextCleaner(config)
            >>> cleaned_docs = preprocessor.process(documents)
        """
        pass


class AsyncPreprocessor(ABC):
    """
    Abstract base class for async text preprocessors.

    Use this for preprocessors that make I/O calls, such as:
    - API calls to external summarization services
    - Database lookups for entity resolution
    - Network requests for metadata enrichment
    """

    @abstractmethod
    async def process(self, documents: list[Document]) -> list[Document]:
        """
        Process documents asynchronously.

        Use async when the preprocessor makes I/O calls. This allows
        concurrent processing of multiple document batches and prevents
        blocking the event loop.

        Args:
            documents: List of documents to process.

        Returns:
            List of processed documents.

        Example:
            >>> preprocessor = AsyncSummarizer(config)
            >>> summarized_docs = await preprocessor.process(documents)
        """
        pass
