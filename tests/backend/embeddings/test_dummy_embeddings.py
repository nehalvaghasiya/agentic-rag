"""
Comprehensive tests for DummyEmbeddings class.

Tests fallback mode embeddings with deterministic hash-based generation.
"""

import pytest
from rag.backend.embeddings.dummy_embeddings import DummyEmbeddings


class TestDummyEmbeddingsInitialization:
    """Test DummyEmbeddings initialization."""

    def test_init_with_default_dimensions(self):
        """Test initialization with default dimensions."""
        embeddings = DummyEmbeddings()
        assert embeddings.dimensions == 1536

    def test_init_with_custom_dimensions(self):
        """Test initialization with custom dimensions."""
        embeddings = DummyEmbeddings(dimensions=384)
        assert embeddings.dimensions == 384

    def test_init_with_large_dimensions(self):
        """Test initialization with large dimensions."""
        embeddings = DummyEmbeddings(dimensions=4096)
        assert embeddings.dimensions == 4096


class TestDummyEmbeddingsDeterminism:
    """Test deterministic embedding generation."""

    def test_same_text_produces_same_embedding(self):
        """Test that same text always produces same embedding."""
        embeddings = DummyEmbeddings(dimensions=384)
        text = "Hello, world!"

        vec1 = embeddings.embed_query(text)
        vec2 = embeddings.embed_query(text)

        assert vec1 == vec2
        assert len(vec1) == 384

    def test_different_text_produces_different_embeddings(self):
        """Test that different text produces different embeddings."""
        embeddings = DummyEmbeddings(dimensions=384)

        vec1 = embeddings.embed_query("Hello")
        vec2 = embeddings.embed_query("World")

        assert vec1 != vec2
        assert len(vec1) == 384
        assert len(vec2) == 384

    def test_embedding_reproducibility_across_instances(self):
        """Test embeddings are reproducible across different instances."""
        text = "Test reproducibility"

        embeddings1 = DummyEmbeddings(dimensions=256)
        embeddings2 = DummyEmbeddings(dimensions=256)

        vec1 = embeddings1.embed_query(text)
        vec2 = embeddings2.embed_query(text)

        assert vec1 == vec2


class TestEmbedQuery:
    """Test embed_query method."""

    def test_embed_simple_query(self):
        """Test embedding a simple query."""
        embeddings = DummyEmbeddings(dimensions=128)
        query = "What is the capital of France?"

        vector = embeddings.embed_query(query)

        assert isinstance(vector, list)
        assert len(vector) == 128
        assert all(isinstance(x, float) for x in vector)

    def test_embed_empty_query(self):
        """Test embedding empty string."""
        embeddings = DummyEmbeddings(dimensions=128)
        vector = embeddings.embed_query("")

        assert len(vector) == 128
        assert all(isinstance(x, float) for x in vector)

    def test_embed_long_query(self):
        """Test embedding a very long query."""
        embeddings = DummyEmbeddings(dimensions=128)
        query = "This is a very long query. " * 100

        vector = embeddings.embed_query(query)

        assert len(vector) == 128

    def test_embed_unicode_query(self):
        """Test embedding query with unicode characters."""
        embeddings = DummyEmbeddings(dimensions=128)
        query = "Hello 世界 🌍 Привет"

        vector = embeddings.embed_query(query)

        assert len(vector) == 128


class TestEmbedDocuments:
    """Test embed_documents method."""

    def test_embed_single_document(self):
        """Test embedding a single document."""
        embeddings = DummyEmbeddings(dimensions=128)
        docs = ["This is a test document."]

        vectors = embeddings.embed_documents(docs)

        assert len(vectors) == 1
        assert len(vectors[0]) == 128
        assert all(isinstance(x, float) for x in vectors[0])

    def test_embed_multiple_documents(self):
        """Test embedding multiple documents."""
        embeddings = DummyEmbeddings(dimensions=128)
        docs = [
            "First document.",
            "Second document.",
            "Third document.",
        ]

        vectors = embeddings.embed_documents(docs)

        assert len(vectors) == 3
        assert all(len(v) == 128 for v in vectors)
        # All should be different
        assert vectors[0] != vectors[1]
        assert vectors[1] != vectors[2]

    def test_embed_empty_document_list(self):
        """Test embedding empty document list."""
        embeddings = DummyEmbeddings(dimensions=128)
        vectors = embeddings.embed_documents([])

        assert vectors == []

    def test_embed_documents_with_empty_strings(self):
        """Test embedding documents containing empty strings."""
        embeddings = DummyEmbeddings(dimensions=128)
        docs = ["", "Valid text", ""]

        vectors = embeddings.embed_documents(docs)

        assert len(vectors) == 3
        assert all(len(v) == 128 for v in vectors)
        # Empty strings should have same embedding
        assert vectors[0] == vectors[2]


class TestVectorNormalization:
    """Test that embeddings are normalized to unit length."""

    def test_vector_is_normalized(self):
        """Test that embedding vector has unit length."""
        embeddings = DummyEmbeddings(dimensions=128)
        vector = embeddings.embed_query("Test normalization")

        # Calculate magnitude
        magnitude = sum(x**2 for x in vector) ** 0.5

        # Should be very close to 1.0 (unit length)
        assert abs(magnitude - 1.0) < 1e-6

    def test_all_vectors_normalized(self):
        """Test that all document embeddings are normalized."""
        embeddings = DummyEmbeddings(dimensions=128)
        docs = ["Doc 1", "Doc 2", "Doc 3"]

        vectors = embeddings.embed_documents(docs)

        for vector in vectors:
            magnitude = sum(x**2 for x in vector) ** 0.5
            assert abs(magnitude - 1.0) < 1e-6


class TestAsyncMethods:
    """Test async embedding methods."""

    @pytest.mark.asyncio
    async def test_aembed_query(self):
        """Test async query embedding."""
        embeddings = DummyEmbeddings(dimensions=128)
        query = "Async test query"

        vector = await embeddings.aembed_query(query)

        assert len(vector) == 128
        assert isinstance(vector, list)

    @pytest.mark.asyncio
    async def test_aembed_documents(self):
        """Test async document embedding."""
        embeddings = DummyEmbeddings(dimensions=128)
        docs = ["Doc 1", "Doc 2", "Doc 3"]

        vectors = await embeddings.aembed_documents(docs)

        assert len(vectors) == 3
        assert all(len(v) == 128 for v in vectors)

    @pytest.mark.asyncio
    async def test_async_matches_sync(self):
        """Test that async methods produce same results as sync."""
        embeddings = DummyEmbeddings(dimensions=128)
        query = "Consistency test"

        sync_vector = embeddings.embed_query(query)
        async_vector = await embeddings.aembed_query(query)

        assert sync_vector == async_vector


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_small_dimensions(self):
        """Test embeddings with very small dimensions."""
        embeddings = DummyEmbeddings(dimensions=2)
        vector = embeddings.embed_query("Test")

        assert len(vector) == 2
        magnitude = sum(x**2 for x in vector) ** 0.5
        assert abs(magnitude - 1.0) < 1e-6

    def test_single_dimension(self):
        """Test embeddings with single dimension."""
        embeddings = DummyEmbeddings(dimensions=1)
        vector = embeddings.embed_query("Test")

        assert len(vector) == 1
        assert abs(abs(vector[0]) - 1.0) < 1e-6  # Should be ±1

    def test_special_characters_in_text(self):
        """Test embedding text with special characters."""
        embeddings = DummyEmbeddings(dimensions=128)
        text = "!@#$%^&*()[]{}|\\;:'\",.<>?/~`"

        vector = embeddings.embed_query(text)

        assert len(vector) == 128

    def test_whitespace_only_text(self):
        """Test embedding whitespace-only text."""
        embeddings = DummyEmbeddings(dimensions=128)
        vector = embeddings.embed_query("   \n\t  ")

        assert len(vector) == 128

    def test_very_long_document(self):
        """Test embedding very long document."""
        embeddings = DummyEmbeddings(dimensions=128)
        long_text = "Lorem ipsum " * 10000

        vector = embeddings.embed_query(long_text)

        assert len(vector) == 128


class TestConsistencyWithDifferentDimensions:
    """Test behavior consistency across different dimensions."""

    @pytest.mark.parametrize("dimensions", [128, 256, 384, 512, 768, 1024, 1536])
    def test_consistent_behavior_across_dimensions(self, dimensions):
        """Test that embeddings work correctly for various dimensions."""
        embeddings = DummyEmbeddings(dimensions=dimensions)
        vector = embeddings.embed_query("Test")

        assert len(vector) == dimensions
        magnitude = sum(x**2 for x in vector) ** 0.5
        assert abs(magnitude - 1.0) < 1e-6
