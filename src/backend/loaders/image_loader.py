"""
Image loader implementation with OCR support.

Loads images and optionally extracts text using Tesseract OCR.
Async I/O for handling large image files efficiently.
"""

from pathlib import Path

import aiofiles
from langchain_core.documents import Document
from loguru import logger
from PIL import Image

from backend.loaders.base import AsyncDocumentLoader
from config import ImageLoaderConfig


class ImageLoader(AsyncDocumentLoader):
    """
    Image loader with OCR support using Tesseract.

    This loader uses async patterns because:
    - Image files can be large (several MB), requiring I/O operations
    - OCR processing is CPU-intensive but file reading is I/O-bound
    - Multiple images may be uploaded concurrently
    - Async file reading prevents blocking during large uploads

    The async approach is particularly beneficial when:
    1. Users upload multiple images at once
    2. Images are fetched from URLs (future enhancement)
    3. Processing large batches of scanned documents

    Attributes:
        config: Image loader configuration including OCR and format settings.
    """

    def __init__(self, config: ImageLoaderConfig) -> None:
        """
        Initialize image loader with configuration.

        Args:
            config: Image loader configuration including OCR settings and
                   supported formats.
        """
        super().__init__(config)
        self.config: ImageLoaderConfig = config
        logger.debug("ImageLoader initialized with config: {}", config.model_dump())

        if self.config.ocr_enabled:
            try:
                import pytesseract  # noqa: F401

                self._tesseract_available = True
                logger.info("Tesseract OCR is available")
            except ImportError:
                self._tesseract_available = False
                logger.warning(
                    "Tesseract OCR is not available. Install pytesseract and tesseract-ocr."
                )

    def supports(self, source: str | Path) -> bool:
        """
        Check if the source is a supported image file.

        Args:
            source: File path to check.

        Returns:
            True if the file has a supported image extension, False otherwise.
        """
        path = Path(source)
        return path.suffix.lower().lstrip(".") in self.config.supported_formats

    async def load(self, source: str | Path) -> list[Document]:
        """
        Load an image and optionally extract text with OCR.

        This is async because:
        1. Reading image files from disk is I/O-bound
        2. Large images take time to load into memory
        3. Enables concurrent processing of multiple images
        4. Won't block other requests during file I/O

        Note: OCR processing itself is CPU-bound (not async), but the file I/O
        operations are async. For production with heavy OCR workloads, consider
        running OCR in a process pool.

        Args:
            source: Path to the image file.

        Returns:
            List containing a single Document with extracted text (if OCR enabled)
            or image metadata.

        Raises:
            FileNotFoundError: If the image file doesn't exist.
            ValueError: If the file is not a supported image format.

        Example:
            >>> loader = ImageLoader(config)
            >>> docs = await loader.load("scanned_document.jpg")
            >>> print(docs[0].page_content)  # Extracted text via OCR
        """
        path = Path(source)

        if not path.exists():
            logger.error("Image file not found: {}", path)
            raise FileNotFoundError(f"Image file not found: {path}")

        if not self.supports(path):
            logger.error("Unsupported image format: {}", path)
            raise ValueError(
                f"Unsupported image format: {path}. Supported: {self.config.supported_formats}"
            )

        logger.info("Loading image: {}", path)

        try:
            # Async file reading for large images
            async with aiofiles.open(path, "rb") as f:
                image_bytes = await f.read()

            # Open image with PIL
            # Note: PIL operations are synchronous and CPU-bound
            from io import BytesIO

            image = Image.open(BytesIO(image_bytes))

            # Extract text with OCR if enabled
            text_content = ""
            if self.config.ocr_enabled and self._tesseract_available:
                import pytesseract

                logger.debug("Running OCR on image: {}", path)
                # OCR is CPU-intensive, runs synchronously
                # For production, consider running in a process pool
                raw_text = pytesseract.image_to_string(image)
                text_content = str(raw_text) if not isinstance(raw_text, str) else raw_text
                logger.info("OCR extracted {} characters from {}", len(text_content), path)
            else:
                text_content = f"Image: {path.name} (OCR not available)"

            # Create document with metadata
            document = Document(
                page_content=text_content,
                metadata={
                    "source_type": "image",
                    "file_path": str(path),
                    "image_format": image.format,
                    "image_size": image.size,
                    "image_mode": image.mode,
                },
            )

            logger.info("Successfully loaded image: {}", path)
            return [document]

        except Exception as e:
            logger.exception("Error loading image {}: {}", path, e)
            raise ValueError(f"Error loading image {path}: {e}") from e
