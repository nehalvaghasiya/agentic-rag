"""
Document loader factory.

Creates appropriate loaders based on source type, following the Factory pattern.
This enables the Open/Closed Principle - new loaders can be added without modifying
existing code.
"""

from pathlib import Path

from loguru import logger

from rag.backend.loaders.base import DocumentLoader
from rag.backend.loaders.docx_loader import DOCXLoader
from rag.backend.loaders.image_loader import ImageLoader
from rag.backend.loaders.pdf_loader import PDFLoader
from rag.backend.loaders.text_loader import TextLoader
from rag.backend.loaders.website_loader import WebsiteLoader
from rag.config import Config


class LoaderFactory:
    """
    Factory for creating document loaders based on source type.

    This class follows the Factory pattern and Open/Closed Principle:
    - Open for extension: New loaders can be registered easily
    - Closed for modification: Existing code doesn't change when adding loaders

    The factory automatically selects the appropriate loader based on the source
    (file extension or URL pattern) and configuration.

    Example:
        >>> factory = LoaderFactory(config)
        >>> loader = factory.get_loader("document.pdf")
        >>> documents = await loader.load("document.pdf")
    """

    def __init__(self, config: Config) -> None:
        """
        Initialize the loader factory with configuration.

        Creates instances of all available loaders based on configuration.
        Disabled loaders are not instantiated.

        Args:
            config: Application configuration containing loader settings.
        """
        self.config = config
        self._loaders: list[DocumentLoader] = []

        # Initialize enabled loaders
        if config.loaders.pdf.enabled:
            self._loaders.append(PDFLoader(config.loaders.pdf))
            logger.debug("Registered PDFLoader")

        if config.loaders.docx.enabled:
            self._loaders.append(DOCXLoader(config.loaders.docx))
            logger.debug("Registered DOCXLoader")

        if config.loaders.text.enabled:
            self._loaders.append(TextLoader(config.loaders.text))
            logger.debug("Registered TextLoader")

        if config.loaders.website.enabled:
            self._loaders.append(WebsiteLoader(config.loaders.website))
            logger.debug("Registered WebsiteLoader")

        if config.loaders.image.enabled:
            self._loaders.append(ImageLoader(config.loaders.image))
            logger.debug("Registered ImageLoader")

        logger.info(f"LoaderFactory initialized with {len(self._loaders)} loaders")

    def get_loader(self, source: str | Path) -> DocumentLoader:
        """
        Get the appropriate loader for the given source.

        Iterates through registered loaders and returns the first one that
        supports the source. This allows for flexible loader selection based
        on file type or URL pattern.

        Args:
            source: Path to file or URL to load from.

        Returns:
            A DocumentLoader instance that can handle the source.

        Raises:
            ValueError: If no loader supports the given source.

        Example:
            >>> factory = LoaderFactory(config)
            >>> # Automatically selects PDFLoader
            >>> loader = factory.get_loader("report.pdf")
            >>> # Automatically selects WebsiteLoader
            >>> loader = factory.get_loader("https://example.com")
        """
        for loader in self._loaders:
            if loader.supports(source):
                logger.debug(f"Selected {loader.__class__.__name__} for {source}")
                return loader

        logger.error(f"No loader found for source: {source}")
        raise ValueError(
            f"No loader available for source: {source}. "
            f"Supported types: PDF, DOCX, TXT, images, websites."
        )

    def register_loader(self, loader: DocumentLoader) -> None:
        """
        Register a new custom loader.

        This method allows for runtime extension of the factory with custom loaders.
        Follows the Open/Closed Principle by allowing extension without modification.

        Args:
            loader: Custom DocumentLoader instance to register.

        Example:
            >>> factory = LoaderFactory(config)
            >>> custom_loader = MyCustomLoader(custom_config)
            >>> factory.register_loader(custom_loader)
            >>> # Now factory can handle sources supported by custom_loader
        """
        self._loaders.append(loader)
        logger.info(f"Registered custom loader: {loader.__class__.__name__}")
