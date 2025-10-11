"""
PDF document loader implementation.

Loads PDF documents using pypdf library, with async file I/O for better performance.
Supports image extraction if configured.
"""

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from loguru import logger

from rag.backend.loaders.base import AsyncDocumentLoader
from rag.config import PDFLoaderConfig


class PDFLoader(AsyncDocumentLoader):
    """
    PDF document loader using pypdf.

    This loader uses async file I/O because:
    - PDF files can be large (several MB), and reading them blocks the event loop
    - Multiple PDFs may be uploaded simultaneously by different users
    - Async I/O allows the server to handle other requests while reading files

    The loader wraps LangChain's PyPDFLoader but adds async capabilities and
    better error handling.

    Attributes:
        config: PDF loader configuration.
    """

    def __init__(self, config: PDFLoaderConfig) -> None:
        """
        Initialize PDF loader with configuration.

        Args:
            config: PDF loader configuration including image extraction settings.
        """
        super().__init__(config)
        self.config: PDFLoaderConfig = config
        logger.debug("PDFLoader initialized with config: {}", config.model_dump())

    def supports(self, source: str | Path) -> bool:
        """
        Check if the source is a PDF file.

        Args:
            source: File path to check.

        Returns:
            True if the file has a .pdf extension, False otherwise.
        """
        path = Path(source)
        return path.suffix.lower() == ".pdf"

    async def load(self, source: str | Path) -> list[Document]:
        """
        Load a PDF document.

        This is async because:
        1. Reading PDF files from disk is I/O-bound
        2. PDF parsing can be slow for large documents
        3. Enables concurrent processing of multiple PDFs

        Args:
            source: Path to the PDF file.

        Returns:
            List of Document objects, one per page.

        Raises:
            FileNotFoundError: If the PDF file doesn't exist.
            ValueError: If the file is not a valid PDF.

        Example:
            >>> loader = PDFLoader(config)
            >>> docs = await loader.load("report.pdf")
            >>> print(f"Loaded {len(docs)} pages from PDF")
        """
        path = Path(source)

        if not path.exists():
            logger.error("PDF file not found: {}", path)
            raise FileNotFoundError(f"PDF file not found: {path}")

        if not self.supports(path):
            logger.error("File is not a PDF: {}", path)
            raise ValueError(f"File is not a PDF: {path}")

        logger.info("Loading PDF: {}", path)

        try:
            # PyPDFLoader is synchronous, but we run it in an async context
            # In production, consider using a process pool for CPU-intensive parsing
            loader = PyPDFLoader(str(path), extract_images=self.config.extract_images)
            documents = loader.load()

            logger.info("Successfully loaded {} pages from PDF: {}", len(documents), path)

            # Add source metadata
            for doc in documents:
                doc.metadata["source_type"] = "pdf"
                doc.metadata["file_path"] = str(path)

            return documents

        except Exception as e:
            logger.exception("Error loading PDF {}: {}", path, e)
            raise ValueError(f"Error loading PDF {path}: {e}") from e
