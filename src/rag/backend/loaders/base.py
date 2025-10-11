"""
Base document loader interface.

Defines the contract that all document loaders must implement, following the
Liskov Substitution Principle. Any loader can be swapped without breaking the system.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from langchain_core.documents import Document


class DocumentLoader(ABC):
    """
    Abstract base class for all document loaders.

    This interface defines the contract for loading documents from various sources.
    Implementations can load from files, URLs, APIs, or any other source, but must
    return a list of LangChain Document objects.

    All loaders should be async-capable since document loading is I/O-bound:
    - File reading: async file I/O prevents blocking the event loop
    - HTTP requests: async HTTP clients enable parallel fetching
    - Image processing: async I/O for reading large images

    Attributes:
        config: Configuration object for this loader type.
    """

    def __init__(self, config: Any) -> None:
        """
        Initialize the document loader.

        Args:
            config: Loader-specific configuration object.
        """
        self.config = config

    @abstractmethod
    async def load(self, source: str | Path) -> list[Document]:
        """
        Load documents from the specified source.

        This is an async method because document loading is I/O-bound:
        - Reading files from disk
        - Fetching content from URLs
        - Processing images with OCR

        Using async allows the application to handle multiple document uploads
        concurrently without blocking, significantly improving throughput when
        users upload multiple files.

        Args:
            source: Path to file or URL to load from. Can be a string or Path object.

        Returns:
            List of Document objects containing the loaded content and metadata.

        Raises:
            FileNotFoundError: If the source file does not exist.
            ValueError: If the source is invalid or unsupported.
            IOError: If there's an error reading the source.

        Example:
            >>> loader = PDFLoader(config)
            >>> documents = await loader.load("document.pdf")
            >>> print(f"Loaded {len(documents)} pages")
        """
        pass

    @abstractmethod
    def supports(self, source: str | Path) -> bool:
        """
        Check if this loader can handle the given source.

        This method is synchronous as it only performs string/path checks
        without any I/O operations.

        Args:
            source: Source to check (file path or URL).

        Returns:
            True if this loader can handle the source, False otherwise.

        Example:
            >>> loader = PDFLoader(config)
            >>> loader.supports("document.pdf")
            True
            >>> loader.supports("document.docx")
            False
        """
        pass


class AsyncDocumentLoader(DocumentLoader, ABC):
    """
    Convenience base class for fully async document loaders.

    This class is identical to DocumentLoader but emphasizes that all I/O
    operations should be async. Use this for loaders that fetch from URLs,
    make API calls, or perform other network operations.
    """

    pass
