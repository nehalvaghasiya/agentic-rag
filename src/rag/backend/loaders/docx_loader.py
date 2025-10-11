"""
DOCX document loader implementation.

Loads Microsoft Word (.docx) documents using python-docx library.
"""

from pathlib import Path

from langchain_community.document_loaders import Docx2txtLoader
from langchain_core.documents import Document
from loguru import logger

from rag.backend.loaders.base import AsyncDocumentLoader
from rag.config import DOCXLoaderConfig


class DOCXLoader(AsyncDocumentLoader):
    """
    DOCX document loader using python-docx.

    This loader uses async patterns because:
    - DOCX files are zip archives that require I/O to extract and parse
    - Multiple users may upload Word documents simultaneously
    - Async I/O prevents blocking other requests during file processing

    Attributes:
        config: DOCX loader configuration.
    """

    def __init__(self, config: DOCXLoaderConfig) -> None:
        """
        Initialize DOCX loader with configuration.

        Args:
            config: DOCX loader configuration.
        """
        super().__init__(config)
        self.config: DOCXLoaderConfig = config
        logger.debug("DOCXLoader initialized")

    def supports(self, source: str | Path) -> bool:
        """
        Check if the source is a DOCX file.

        Args:
            source: File path to check.

        Returns:
            True if the file has a .docx extension, False otherwise.
        """
        path = Path(source)
        return path.suffix.lower() == ".docx"

    async def load(self, source: str | Path) -> list[Document]:
        """
        Load a DOCX document.

        This is async because:
        1. Reading DOCX files involves unzipping and parsing XML (I/O-bound)
        2. Enables concurrent processing of multiple Word documents
        3. Won't block other API requests during file processing

        Args:
            source: Path to the DOCX file.

        Returns:
            List containing a single Document with the full text content.

        Raises:
            FileNotFoundError: If the DOCX file doesn't exist.
            ValueError: If the file is not a valid DOCX.

        Example:
            >>> loader = DOCXLoader(config)
            >>> docs = await loader.load("report.docx")
            >>> print(docs[0].page_content)
        """
        path = Path(source)

        if not path.exists():
            logger.error("DOCX file not found: {}", path)
            raise FileNotFoundError(f"DOCX file not found: {path}")

        if not self.supports(path):
            logger.error("File is not a DOCX: {}", path)
            raise ValueError(f"File is not a DOCX: {path}")

        logger.info("Loading DOCX: {}", path)

        try:
            # Docx2txtLoader is synchronous, but we run it in an async context
            loader = Docx2txtLoader(str(path))
            documents = loader.load()

            logger.info("Successfully loaded DOCX: {}", path)

            # Add source metadata
            for doc in documents:
                doc.metadata["source_type"] = "docx"
                doc.metadata["file_path"] = str(path)

            return documents

        except Exception as e:
            logger.exception("Error loading DOCX {}: {}", path, e)
            raise ValueError(f"Error loading DOCX {path}: {e}") from e
