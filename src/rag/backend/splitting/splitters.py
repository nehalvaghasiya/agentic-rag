"""
Text splitter implementations.

Provides various splitting strategies: recursive, character, token, and semantic.
"""

from langchain_core.documents import Document
from langchain_text_splitters import (
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
    TokenTextSplitter,
)
from loguru import logger

from rag.backend.splitting.base import TextSplitter
from rag.config import (
    CharacterSplitterConfig,
    RecursiveSplitterConfig,
    SemanticSplitterConfig,
    SplittingConfig,
    TokenSplitterConfig,
)


class RecursiveSplitter(TextSplitter):
    """
    Recursive character text splitter.

    Splits text recursively using a hierarchy of separators. This is the most
    common and recommended splitter for general use.

    Synchronous because splitting is CPU-bound string manipulation.
    """

    def __init__(self, config: RecursiveSplitterConfig) -> None:
        """Initialize recursive splitter with configuration."""
        self.config = config
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            separators=config.separators,
            length_function=len,
        )
        logger.debug("RecursiveSplitter initialized: chunk_size={}", config.chunk_size)

    def split_documents(self, documents: list[Document]) -> list[Document]:
        """Split documents recursively."""
        logger.info(f"Splitting {len(documents)} documents with RecursiveSplitter")
        chunks = self._splitter.split_documents(documents)
        logger.info(f"Created {len(chunks)} chunks")
        return chunks


class CharacterSplitter(TextSplitter):
    """
    Simple character-based text splitter.

    Splits text based on a single separator. Simpler than recursive but less flexible.
    Synchronous CPU-bound operation.
    """

    def __init__(self, config: CharacterSplitterConfig) -> None:
        """Initialize character splitter with configuration."""
        self.config = config
        self._splitter = CharacterTextSplitter(
            separator=config.separator,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
            length_function=len,
        )
        logger.debug("CharacterSplitter initialized: separator={}", config.separator)

    def split_documents(self, documents: list[Document]) -> list[Document]:
        """Split documents by character."""
        logger.info(f"Splitting {len(documents)} documents with CharacterSplitter")
        chunks = self._splitter.split_documents(documents)
        logger.info(f"Created {len(chunks)} chunks")
        return chunks


class TokenSplitter(TextSplitter):
    """
    Token-based text splitter.

    Splits text based on token count (using tiktoken encoding). Useful for LLMs
    with token limits.

    Synchronous CPU-bound operation.
    """

    def __init__(self, config: TokenSplitterConfig) -> None:
        """Initialize token splitter with configuration."""
        self.config = config
        self._splitter = TokenTextSplitter(
            encoding_name=config.encoding_name,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )
        logger.debug("TokenSplitter initialized: encoding={}", config.encoding_name)

    def split_documents(self, documents: list[Document]) -> list[Document]:
        """Split documents by tokens."""
        logger.info(f"Splitting {len(documents)} documents with TokenSplitter")
        chunks = self._splitter.split_documents(documents)
        logger.info(f"Created {len(chunks)} chunks")
        return chunks


class SemanticSplitter(TextSplitter):
    """
    Semantic text splitter.

    Splits text based on semantic similarity between sentences. More intelligent
    than simple character/token splitting.

    Note: This requires embeddings, so it may have some I/O if using API-based
    embeddings, but the core splitting logic is still synchronous.
    """

    def __init__(self, config: SemanticSplitterConfig, embeddings) -> None:
        """
        Initialize semantic splitter with configuration and embeddings.

        Args:
            config: Semantic splitter configuration.
            embeddings: Embeddings model to use for semantic similarity.
        """
        self.config = config
        self.embeddings = embeddings

        from langchain_experimental.text_splitter import SemanticChunker

        self._splitter = SemanticChunker(
            embeddings=embeddings,
            buffer_size=config.buffer_size,
            breakpoint_threshold_type=config.breakpoint_threshold_type,
        )
        logger.debug("SemanticSplitter initialized")

    def split_documents(self, documents: list[Document]) -> list[Document]:
        """Split documents semantically."""
        logger.info(f"Splitting {len(documents)} documents with SemanticSplitter")
        chunks = self._splitter.split_documents(documents)
        logger.info(f"Created {len(chunks)} chunks")
        return chunks


def create_splitter(config: SplittingConfig, embeddings=None) -> TextSplitter:
    """
    Factory function to create the appropriate splitter based on configuration.

    Args:
        config: Splitting configuration specifying strategy and parameters.
        embeddings: Embeddings model (required for semantic splitter only).

    Returns:
        Configured TextSplitter instance.

    Raises:
        ValueError: If semantic strategy is selected but embeddings not provided.

    Example:
        >>> splitter = create_splitter(config.splitting)
        >>> chunks = splitter.split_documents(documents)
    """
    if config.strategy == "recursive":
        return RecursiveSplitter(config.recursive)
    elif config.strategy == "character":
        return CharacterSplitter(config.character)
    elif config.strategy == "token":
        return TokenSplitter(config.token)
    elif config.strategy == "semantic":
        if embeddings is None:
            raise ValueError("Embeddings required for semantic splitting")
        return SemanticSplitter(config.semantic, embeddings)
    else:
        raise ValueError(f"Unknown splitting strategy: {config.strategy}")
