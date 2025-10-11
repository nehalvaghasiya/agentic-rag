"""
Text cleaning preprocessor.

Cleans and normalizes text in documents.
"""

import re

from langchain_core.documents import Document
from loguru import logger

from rag.backend.preprocessing.base import Preprocessor
from rag.config import CleaningConfig


class TextCleaner(Preprocessor):
    """
    Text cleaning preprocessor.

    Performs various text cleaning operations such as:
    - Removing extra whitespace
    - Normalizing line breaks
    - Optionally removing special characters
    - Optionally converting to lowercase

    This is synchronous because all operations are CPU-bound string manipulations.
    No I/O operations are performed.

    Attributes:
        config: Text cleaning configuration.
    """

    def __init__(self, config: CleaningConfig) -> None:
        """
        Initialize text cleaner with configuration.

        Args:
            config: Cleaning configuration specifying which operations to perform.
        """
        self.config = config
        logger.debug("TextCleaner initialized with config: {}", config.model_dump())

    def process(self, documents: list[Document]) -> list[Document]:
        """
        Clean text in all documents.

        Applies configured cleaning operations to each document's content.
        This is CPU-bound and synchronous.

        Args:
            documents: List of documents to clean.

        Returns:
            List of documents with cleaned text.

        Example:
            >>> cleaner = TextCleaner(config)
            >>> cleaned = cleaner.process(documents)
        """
        logger.info(f"Cleaning {len(documents)} documents")

        cleaned_docs = []
        for doc in documents:
            cleaned_text = doc.page_content

            # Remove extra whitespace
            if self.config.remove_extra_whitespace:
                cleaned_text = self._remove_extra_whitespace(cleaned_text)

            # Remove special characters
            if self.config.remove_special_chars:
                cleaned_text = self._remove_special_chars(cleaned_text)

            # Convert to lowercase
            if self.config.lowercase:
                cleaned_text = cleaned_text.lower()

            # Create new document with cleaned text
            cleaned_doc = Document(
                page_content=cleaned_text,
                metadata=doc.metadata.copy(),
            )
            cleaned_docs.append(cleaned_doc)

        logger.info(f"Cleaned {len(cleaned_docs)} documents")
        return cleaned_docs

    def _remove_extra_whitespace(self, text: str) -> str:
        """
        Remove extra whitespace from text.

        Replaces multiple spaces with single space, removes leading/trailing
        whitespace, and normalizes line breaks.

        Args:
            text: Text to clean.

        Returns:
            Text with normalized whitespace.
        """
        # Replace multiple spaces with single space
        text = re.sub(r" +", " ", text)

        # Replace multiple newlines with double newline
        text = re.sub(r"\n\n+", "\n\n", text)

        # Remove leading/trailing whitespace
        text = text.strip()

        return text

    def _remove_special_chars(self, text: str) -> str:
        """
        Remove special characters from text.

        Keeps only alphanumeric characters, whitespace, and common punctuation.

        Args:
            text: Text to clean.

        Returns:
            Text with special characters removed.
        """
        # Keep alphanumeric, whitespace, and basic punctuation
        text = re.sub(r"[^a-zA-Z0-9\s.,!?;:()\-'\"]", "", text)
        return text
