"""
Website content loader implementation.

Loads content from websites using Playwright for JavaScript-enabled pages.
Fully async for non-blocking HTTP requests.
"""

from pathlib import Path
from urllib.parse import urlparse

import httpx
from langchain_community.document_loaders import PlaywrightURLLoader
from langchain_core.documents import Document
from loguru import logger

from backend.loaders.base import AsyncDocumentLoader
from config import WebsiteLoaderConfig


class WebsiteLoader(AsyncDocumentLoader):
    """
    Website content loader using Playwright.

    This loader is fully async because:
    - HTTP requests are inherently I/O-bound and network-dependent
    - Multiple URLs may need to be fetched concurrently
    - Playwright supports async operations natively
    - Prevents blocking the event loop during slow network requests

    Using async HTTP allows us to:
    1. Fetch multiple pages in parallel (e.g., when crawling a site)
    2. Handle timeouts gracefully without blocking other requests
    3. Scale to many concurrent users fetching different websites

    Attributes:
        config: Website loader configuration including timeout and user agent.
    """

    def __init__(self, config: WebsiteLoaderConfig) -> None:
        """
        Initialize website loader with configuration.

        Args:
            config: Website loader configuration including timeout, user agent,
                   and maximum pages to fetch.
        """
        super().__init__(config)
        self.config: WebsiteLoaderConfig = config
        logger.debug("WebsiteLoader initialized with config: {}", config.model_dump())

    def supports(self, source: str | Path) -> bool:
        """
        Check if the source is a valid URL.

        Args:
            source: URL string to check.

        Returns:
            True if the source is a valid HTTP/HTTPS URL, False otherwise.
        """
        try:
            result = urlparse(str(source))
            return result.scheme in ("http", "https") and bool(result.netloc)
        except Exception:
            return False

    async def load(self, source: str | Path) -> list[Document]:
        """
        Load content from a website.

        This is async because:
        1. HTTP requests are I/O-bound and may take seconds to complete
        2. JavaScript rendering with Playwright is async
        3. Multiple pages may be loaded concurrently
        4. Network timeouts need to be handled without blocking

        The async approach allows the server to handle other requests while
        waiting for the website to respond, significantly improving throughput.

        Args:
            source: URL of the website to load.

        Returns:
            List of Document objects containing the page content and metadata.

        Raises:
            ValueError: If the URL is invalid or unreachable.
            TimeoutError: If the request exceeds the configured timeout.

        Example:
            >>> loader = WebsiteLoader(config)
            >>> docs = await loader.load("https://example.com")
            >>> print(docs[0].page_content[:100])
        """
        url = str(source)

        if not self.supports(url):
            logger.error("Invalid URL: {}", url)
            raise ValueError(f"Invalid URL: {url}")

        logger.info("Loading website: {}", url)

        try:
            # First, do a quick async HEAD request to check if URL is reachable
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                try:
                    response = await client.head(url, follow_redirects=True)
                    response.raise_for_status()
                except httpx.HTTPError as e:
                    logger.error("URL not reachable: {} - {}", url, e)
                    raise ValueError(f"URL not reachable: {url}") from e

            # Use Playwright to load the page (handles JavaScript rendering)
            # Note: PlaywrightURLLoader is not fully async in LangChain, but we
            # run it in an async context. For production, consider using
            # playwright.async_api directly for better async support.
            loader = PlaywrightURLLoader(
                urls=[url],
                remove_selectors=["script", "style"],
                headless=True,
            )
            documents = await self._async_load_playwright(loader)

            logger.info("Successfully loaded website: {}", url)

            # Add source metadata
            for doc in documents:
                doc.metadata["source_type"] = "website"
                doc.metadata["url"] = url

            return documents

        except Exception as e:
            logger.exception("Error loading website {}: {}", url, e)
            raise ValueError(f"Error loading website {url}: {e}") from e

    async def _async_load_playwright(self, loader: PlaywrightURLLoader) -> list[Document]:
        """
        Helper to run Playwright loader in async context.

        This wraps the synchronous Playwright loader to work in an async context.
        In production, you might want to use Playwright's async API directly.

        Args:
            loader: PlaywrightURLLoader instance.

        Returns:
            List of loaded documents.
        """
        # For now, we run the sync loader in the async context
        # In production, use playwright.async_api for true async
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, loader.load)
