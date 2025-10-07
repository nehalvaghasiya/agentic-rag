"""
Plain text document loader.

Loads content from .txt files with support for various encodings.
"""

from pathlib import Path

from langchain_core.documents import Document
from loguru import logger

from backend.loaders.base import DocumentLoader


class TextLoader(DocumentLoader):
    """
    Loader for plain text files (.txt).

    Supports various text encodings and handles large files efficiently.
    Useful for loading markdown, code files, logs, and other plain text content.

    Example:
        >>> loader = TextLoader(config)
        >>> documents = await loader.load("notes.txt")
        >>> print(documents[0].page_content)
    """

    SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".log", ".csv", ".json"}

    async def load(self, source: str | Path) -> list[Document]:
        """
        Load text content from a file.

        This is async to handle large files without blocking the event loop.
        Uses aiofiles for async file I/O.

        Args:
            source: Path to the text file.

        Returns:
            List containing a single Document with the text content.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            UnicodeDecodeError: If the file encoding is not supported.
            IOError: If there's an error reading the file.

        Example:
            >>> loader = TextLoader(config)
            >>> docs = await loader.load("document.txt")
            >>> print(f"Loaded {len(docs[0].page_content)} characters")
        """
        source_path = Path(source)

        if not source_path.exists():
            logger.error(f"Text file not found: {source_path}")
            raise FileNotFoundError(f"File not found: {source_path}")

        logger.info(f"Loading text file: {source_path}")

        try:
            # Try common encodings
            encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
            content = None
            encoding_used = None

            for encoding in encodings:
                try:
                    # Use synchronous file reading for now
                    # TODO: Consider aiofiles for truly async I/O
                    with open(source_path, encoding=encoding) as f:
                        content = f.read()
                    encoding_used = encoding
                    logger.debug(f"Successfully read file with {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                raise UnicodeDecodeError(
                    "utf-8", b"", 0, 1, f"Could not decode file with any of: {encodings}"
                )

            # Create document with metadata
            metadata = {
                "source": str(source_path),
                "file_name": source_path.name,
                "file_extension": source_path.suffix,
                "encoding": encoding_used,
                "file_size_bytes": source_path.stat().st_size,
            }

            document = Document(
                page_content=content,
                metadata=metadata,
            )

            logger.info(
                f"Loaded text file: {source_path.name} ({len(content)} chars, {encoding_used})"
            )

            return [document]

        except Exception as e:
            logger.exception(f"Error loading text file {source_path}: {e}")
            raise

    def supports(self, source: str | Path) -> bool:
        """
        Check if this loader supports the given source.

        Supports .txt and other common text file extensions.

        Args:
            source: File path to check.

        Returns:
            True if the file has a supported text extension.

        Example:
            >>> loader = TextLoader(config)
            >>> loader.supports("document.txt")
            True
            >>> loader.supports("notes.md")
            True
            >>> loader.supports("image.jpg")
            False
        """
        source_path = Path(source)
        is_supported = source_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

        if is_supported:
            logger.debug(f"TextLoader supports: {source_path}")

        return is_supported
