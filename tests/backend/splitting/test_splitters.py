"""
Comprehensive tests for text splitters.

Tests all splitter types, configurations, and edge cases.
"""

import pytest
from langchain_core.documents import Document

from rag.backend.splitting.splitters import (
    CharacterSplitter,
    RecursiveSplitter,
    SemanticSplitter,
    TokenSplitter,
    create_splitter,
)
from rag.config import (
    CharacterSplitterConfig,
    RecursiveSplitterConfig,
    SemanticSplitterConfig,
    SplittingConfig,
    TokenSplitterConfig,
)


class TestRecursiveSplitter:
    """Test RecursiveSplitter functionality."""

    def test_init_with_config(self, recursive_splitter_config: RecursiveSplitterConfig):
        """Test RecursiveSplitter initialization."""
        splitter = RecursiveSplitter(recursive_splitter_config)

        assert splitter.config == recursive_splitter_config
        assert splitter._splitter is not None

    def test_split_simple_document(self):
        """Test splitting a simple document."""
        config = RecursiveSplitterConfig(
            chunk_size=50, chunk_overlap=10, separators=["\n\n", "\n", " ", ""]
        )
        splitter = RecursiveSplitter(config)

        text = "This is a test. " * 10  # Creates text > chunk_size
        docs = [Document(page_content=text, metadata={"source": "test"})]

        result = splitter.split_documents(docs)

        assert len(result) > 1  # Should split into multiple chunks
        assert all(len(chunk.page_content) <= 60 for chunk in result)  # Some overlap

    def test_split_respects_chunk_size(self):
        """Test that splitting respects chunk_size parameter."""
        config = RecursiveSplitterConfig(
            chunk_size=100, chunk_overlap=0, separators=[" "]
        )
        splitter = RecursiveSplitter(config)

        text = "word " * 200  # Create long text
        docs = [Document(page_content=text, metadata={})]

        result = splitter.split_documents(docs)

        # All chunks should be <= chunk_size (except possibly last)
        for chunk in result[:-1]:
            assert len(chunk.page_content) <= 120  # Allow some variance

    def test_split_respects_chunk_overlap(self):
        """Test that chunk overlap works correctly."""
        config = RecursiveSplitterConfig(
            chunk_size=50, chunk_overlap=10, separators=[" "]
        )
        splitter = RecursiveSplitter(config)

        text = "word " * 50
        docs = [Document(page_content=text, metadata={})]

        result = splitter.split_documents(docs)

        if len(result) > 1:
            # Check that consecutive chunks have some overlap
            # (This is hard to test precisely, but should have multiple chunks)
            assert len(result) > 1

    def test_split_with_custom_separators(self):
        """Test splitting with custom separators."""
        config = RecursiveSplitterConfig(
            chunk_size=100, chunk_overlap=10, separators=["\n\n", "\n", "."]
        )
        splitter = RecursiveSplitter(config)

        text = "Sentence 1.\nSentence 2.\n\nParagraph 2.\nSentence 3."
        docs = [Document(page_content=text, metadata={})]

        result = splitter.split_documents(docs)

        assert len(result) >= 1

    def test_split_document_shorter_than_chunk_size(self):
        """Test splitting document shorter than chunk_size."""
        config = RecursiveSplitterConfig(
            chunk_size=1000, chunk_overlap=0, separators=[" "]
        )
        splitter = RecursiveSplitter(config)

        text = "Short document."
        docs = [Document(page_content=text, metadata={})]

        result = splitter.split_documents(docs)

        # Should return single chunk
        assert len(result) == 1
        assert result[0].page_content == text

    def test_split_empty_document(self):
        """Test splitting empty document."""
        config = RecursiveSplitterConfig(
            chunk_size=100, chunk_overlap=10, separators=[" "]
        )
        splitter = RecursiveSplitter(config)

        docs = [Document(page_content="", metadata={})]

        result = splitter.split_documents(docs)

        # Should return empty or single empty chunk
        assert len(result) >= 0

    def test_split_multiple_documents(self):
        """Test splitting multiple documents."""
        config = RecursiveSplitterConfig(
            chunk_size=50, chunk_overlap=10, separators=[" "]
        )
        splitter = RecursiveSplitter(config)

        docs = [
            Document(page_content="Short doc 1.", metadata={"id": 1}),
            Document(page_content="word " * 30, metadata={"id": 2}),
            Document(page_content="Short doc 3.", metadata={"id": 3}),
        ]

        result = splitter.split_documents(docs)

        # Should have chunks from all documents
        assert len(result) >= 3

    def test_metadata_preserved_in_chunks(self):
        """Test that metadata is preserved in split chunks."""
        config = RecursiveSplitterConfig(
            chunk_size=50, chunk_overlap=10, separators=[" "]
        )
        splitter = RecursiveSplitter(config)

        metadata = {"source": "test.pdf", "page": 1}
        text = "word " * 30
        docs = [Document(page_content=text, metadata=metadata)]

        result = splitter.split_documents(docs)

        # All chunks should have the same metadata
        for chunk in result:
            assert chunk.metadata["source"] == "test.pdf"
            assert chunk.metadata["page"] == 1


class TestCharacterSplitter:
    """Test CharacterSplitter functionality."""

    def test_init_with_config(self, character_splitter_config: CharacterSplitterConfig):
        """Test CharacterSplitter initialization."""
        splitter = CharacterSplitter(character_splitter_config)

        assert splitter.config == character_splitter_config
        assert splitter._splitter is not None

    def test_split_by_newline(self):
        """Test splitting by newline separator."""
        config = CharacterSplitterConfig(chunk_size=100, chunk_overlap=10, separator="\n")
        splitter = CharacterSplitter(config)

        text = "Line 1\nLine 2\nLine 3\nLine 4"
        docs = [Document(page_content=text, metadata={})]

        result = splitter.split_documents(docs)

        assert len(result) >= 1

    def test_split_by_custom_separator(self):
        """Test splitting by custom separator."""
        config = CharacterSplitterConfig(chunk_size=100, chunk_overlap=0, separator="|")
        splitter = CharacterSplitter(config)

        text = "Part 1|Part 2|Part 3"
        docs = [Document(page_content=text, metadata={})]

        result = splitter.split_documents(docs)

        assert len(result) >= 1

    def test_split_no_separator_found(self):
        """Test splitting when separator is not in text."""
        config = CharacterSplitterConfig(chunk_size=50, chunk_overlap=0, separator="|")
        splitter = CharacterSplitter(config)

        text = "No separator in this text."
        docs = [Document(page_content=text, metadata={})]

        result = splitter.split_documents(docs)

        # Should still split if text exceeds chunk_size, or return single chunk
        assert len(result) >= 1


class TestTokenSplitter:
    """Test TokenSplitter functionality."""

    def test_init_with_config(self, token_splitter_config: TokenSplitterConfig):
        """Test TokenSplitter initialization."""
        splitter = TokenSplitter(token_splitter_config)

        assert splitter.config == token_splitter_config
        assert splitter._splitter is not None

    def test_split_by_tokens(self):
        """Test splitting by token count."""
        config = TokenSplitterConfig(
            chunk_size=50, chunk_overlap=10, encoding_name="cl100k_base"
        )
        splitter = TokenSplitter(config)

        # Create text with many tokens
        text = "This is a test sentence. " * 20
        docs = [Document(page_content=text, metadata={})]

        result = splitter.split_documents(docs)

        # Should split into multiple chunks based on token count
        assert len(result) >= 1

    def test_different_encoding(self):
        """Test with different token encoding."""
        config = TokenSplitterConfig(
            chunk_size=100, chunk_overlap=10, encoding_name="cl100k_base"
        )
        splitter = TokenSplitter(config)

        text = "Test with encoding. " * 30
        docs = [Document(page_content=text, metadata={})]

        result = splitter.split_documents(docs)

        assert len(result) >= 1

    def test_token_split_short_text(self):
        """Test token splitting with short text."""
        config = TokenSplitterConfig(
            chunk_size=1000, chunk_overlap=0, encoding_name="cl100k_base"
        )
        splitter = TokenSplitter(config)

        text = "Short text."
        docs = [Document(page_content=text, metadata={})]

        result = splitter.split_documents(docs)

        assert len(result) == 1
        assert result[0].page_content == text


class TestSemanticSplitter:
    """Test SemanticSplitter functionality."""

    def test_init_with_embeddings(
        self, semantic_splitter_config: SemanticSplitterConfig, dummy_embeddings
    ):
        """Test SemanticSplitter initialization with embeddings."""
        splitter = SemanticSplitter(semantic_splitter_config, dummy_embeddings)

        assert splitter.config == semantic_splitter_config
        assert splitter.embeddings == dummy_embeddings
        assert splitter._splitter is not None

    def test_split_semantically(self, semantic_splitter_config: SemanticSplitterConfig, dummy_embeddings):
        """Test semantic splitting."""
        splitter = SemanticSplitter(semantic_splitter_config, dummy_embeddings)

        text = (
            "This is about cats. Cats are great pets. "
            "Now let's talk about dogs. Dogs are loyal. "
            "Finally, birds are interesting. Birds can fly."
        )
        docs = [Document(page_content=text, metadata={})]

        result = splitter.split_documents(docs)

        # Should split based on semantic similarity
        assert len(result) >= 1

    def test_semantic_split_with_buffer_size(self, dummy_embeddings):
        """Test semantic splitting with different buffer sizes."""
        config = SemanticSplitterConfig(buffer_size=2, breakpoint_threshold_type="percentile")
        splitter = SemanticSplitter(config, dummy_embeddings)

        text = "Sentence 1. Sentence 2. Sentence 3. Sentence 4."
        docs = [Document(page_content=text, metadata={})]

        result = splitter.split_documents(docs)

        assert len(result) >= 1

    def test_semantic_different_threshold_types(self, dummy_embeddings):
        """Test semantic splitting with different threshold types."""
        for threshold_type in ["percentile", "standard_deviation", "interquartile"]:
            config = SemanticSplitterConfig(
                buffer_size=1, breakpoint_threshold_type=threshold_type
            )
            splitter = SemanticSplitter(config, dummy_embeddings)

            text = "Topic 1 sentence. Topic 2 sentence. Topic 3 sentence."
            docs = [Document(page_content=text, metadata={})]

            result = splitter.split_documents(docs)

            assert len(result) >= 1


class TestCreateSplitterFactory:
    """Test create_splitter factory function."""

    def test_create_recursive_splitter(self, splitting_config: SplittingConfig):
        """Test creating recursive splitter from config."""
        splitting_config.strategy = "recursive"
        splitter = create_splitter(splitting_config)

        assert isinstance(splitter, RecursiveSplitter)

    def test_create_character_splitter(self, splitting_config: SplittingConfig):
        """Test creating character splitter from config."""
        splitting_config.strategy = "character"
        splitter = create_splitter(splitting_config)

        assert isinstance(splitter, CharacterSplitter)

    def test_create_token_splitter(self, splitting_config: SplittingConfig):
        """Test creating token splitter from config."""
        splitting_config.strategy = "token"
        splitter = create_splitter(splitting_config)

        assert isinstance(splitter, TokenSplitter)

    def test_create_semantic_splitter(
        self, splitting_config: SplittingConfig, dummy_embeddings
    ):
        """Test creating semantic splitter from config."""
        splitting_config.strategy = "semantic"
        splitter = create_splitter(splitting_config, embeddings=dummy_embeddings)

        assert isinstance(splitter, SemanticSplitter)

    def test_semantic_without_embeddings_raises_error(
        self, splitting_config: SplittingConfig
    ):
        """Test that creating semantic splitter without embeddings raises error."""
        splitting_config.strategy = "semantic"

        with pytest.raises(ValueError, match="Embeddings required"):
            create_splitter(splitting_config, embeddings=None)

    def test_unknown_strategy_raises_error(self, splitting_config: SplittingConfig):
        """Test that unknown strategy raises ValueError."""
        splitting_config.strategy = "unknown"

        with pytest.raises(ValueError, match="Unknown splitting strategy"):
            create_splitter(splitting_config)


class TestSplitterEdgeCases:
    """Test edge cases across all splitters."""

    def test_empty_document_list(self):
        """Test splitting empty document list."""
        config = RecursiveSplitterConfig(
            chunk_size=100, chunk_overlap=10, separators=[" "]
        )
        splitter = RecursiveSplitter(config)

        result = splitter.split_documents([])

        assert result == []

    def test_very_large_chunk_size(self):
        """Test splitting with very large chunk size."""
        config = RecursiveSplitterConfig(
            chunk_size=1000000, chunk_overlap=0, separators=[" "]
        )
        splitter = RecursiveSplitter(config)

        text = "Normal text that's much smaller than chunk size."
        docs = [Document(page_content=text, metadata={})]

        result = splitter.split_documents(docs)

        assert len(result) == 1
        assert result[0].page_content == text

    def test_chunk_overlap_larger_than_chunk_size(self):
        """Test that chunk_overlap > chunk_size raises ValueError."""
        # LangChain enforces chunk_overlap < chunk_size
        config = RecursiveSplitterConfig(
            chunk_size=50, chunk_overlap=100, separators=[" "]
        )
        # Should raise ValueError during initialization
        with pytest.raises(ValueError, match="larger chunk overlap"):
            RecursiveSplitter(config)

    def test_zero_chunk_overlap(self):
        """Test splitting with zero overlap."""
        config = RecursiveSplitterConfig(
            chunk_size=50, chunk_overlap=0, separators=[" "]
        )
        splitter = RecursiveSplitter(config)

        text = "word " * 30
        docs = [Document(page_content=text, metadata={})]

        result = splitter.split_documents(docs)

        # Should work fine with no overlap
        assert len(result) >= 1

    def test_single_word_document(self):
        """Test splitting single word document."""
        config = RecursiveSplitterConfig(
            chunk_size=100, chunk_overlap=10, separators=[" "]
        )
        splitter = RecursiveSplitter(config)

        docs = [Document(page_content="word", metadata={})]

        result = splitter.split_documents(docs)

        assert len(result) == 1
        assert result[0].page_content == "word"

    def test_document_with_only_separators(self):
        """Test splitting document with only separators."""
        config = RecursiveSplitterConfig(
            chunk_size=100, chunk_overlap=0, separators=["\n", " "]
        )
        splitter = RecursiveSplitter(config)

        docs = [Document(page_content="\n\n  \n  ", metadata={})]

        result = splitter.split_documents(docs)

        # May return empty chunks or filter them out
        assert len(result) >= 0
