"""
Comprehensive tests for AsyncPGVectorStore.

Tests vector storage and retrieval with boundary and edge cases.
Note: These tests use mocks to avoid requiring an actual PostgreSQL database.
"""

import pytest
from unittest.mock import AsyncMock, Mock, MagicMock, patch
from langchain_core.documents import Document

from rag.backend.vectorstore.pgvector_store import AsyncPGVectorStore, create_vectorstore
from rag.backend.embeddings.dummy_embeddings import DummyEmbeddings
from rag.config import PGVectorConfig


class TestAsyncPGVectorStoreInitialization:
    """Test AsyncPGVectorStore initialization."""

    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    def test_init_creates_instance(self, mock_pgvector, mock_get_api_key):
        """Test that AsyncPGVectorStore can be instantiated."""
        mock_get_api_key.return_value = "test_password"
        embeddings = DummyEmbeddings(dimensions=384)
        config = PGVectorConfig(
            host="localhost",
            port=5432,
            database="test_db",
            user="test_user",
            password_env="TEST_PASSWORD",
            collection_name="test_collection"
        )

        store = AsyncPGVectorStore(config, embeddings)

        assert store is not None
        assert store.config == config
        assert store.embeddings == embeddings

    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    def test_connection_string_format(self, mock_pgvector, mock_get_api_key):
        """Test that connection string is correctly formatted."""
        mock_get_api_key.return_value = "secret_password"
        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="db.example.com",
            port=5433,
            database="my_db",
            user="my_user",
            password_env="DB_PASSWORD",
            collection_name="vectors"
        )

        store = AsyncPGVectorStore(config, embeddings)

        expected = "postgresql+psycopg://my_user:secret_password@db.example.com:5433/my_db"
        assert store.connection_string == expected

    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    def test_init_with_custom_collection_name(self, mock_pgvector, mock_get_api_key):
        """Test initialization with custom collection name."""
        mock_get_api_key.return_value = "password"
        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost",
            port=5432,
            database="db",
            user="user",
            password_env="PWD",
            collection_name="custom_vectors"
        )

        store = AsyncPGVectorStore(config, embeddings)

        # Verify PGVector was initialized with correct collection name
        mock_pgvector.assert_called_once()
        call_kwargs = mock_pgvector.call_args.kwargs
        assert call_kwargs['collection_name'] == "custom_vectors"


class TestAddDocuments:
    """Test add_documents method."""

    @pytest.mark.asyncio
    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    @patch('rag.backend.embeddings.embeddings.embed_documents_async')
    async def test_add_single_document(self, mock_embed, mock_pgvector, mock_get_api_key):
        """Test adding a single document."""
        mock_get_api_key.return_value = "password"
        mock_embed.return_value = [[0.1, 0.2, 0.3]]
        
        mock_vectorstore = Mock()
        mock_vectorstore.add_documents = Mock(return_value=["doc_1"])
        mock_pgvector.return_value = mock_vectorstore

        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )
        store = AsyncPGVectorStore(config, embeddings)

        docs = [Document(page_content="Test content", metadata={"source": "test"})]
        
        # Mock event loop for run_in_executor
        async def mock_executor(executor, func, *args):
            return func(*args)
        mock_loop = Mock()
        mock_loop.run_in_executor = mock_executor
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            ids = await store.add_documents(docs)

        assert ids == ["doc_1"]
        assert len(ids) == 1

    @pytest.mark.asyncio
    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    @patch('rag.backend.embeddings.embeddings.embed_documents_async')
    async def test_add_multiple_documents(self, mock_embed, mock_pgvector, mock_get_api_key):
        """Test adding multiple documents."""
        mock_get_api_key.return_value = "password"
        mock_embed.return_value = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
        
        mock_vectorstore = Mock()
        mock_vectorstore.add_documents = Mock(return_value=["doc_1", "doc_2", "doc_3"])
        mock_pgvector.return_value = mock_vectorstore

        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )
        store = AsyncPGVectorStore(config, embeddings)

        docs = [
            Document(page_content="Doc 1", metadata={}),
            Document(page_content="Doc 2", metadata={}),
            Document(page_content="Doc 3", metadata={}),
        ]
        
        # Mock event loop for run_in_executor
        async def mock_executor(executor, func, *args):
            return func(*args)
        mock_loop = Mock()
        mock_loop.run_in_executor = mock_executor
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            ids = await store.add_documents(docs)

        assert len(ids) == 3
        assert ids == ["doc_1", "doc_2", "doc_3"]

    @pytest.mark.asyncio
    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    @patch('rag.backend.embeddings.embeddings.embed_documents_async')
    async def test_add_empty_document_list(self, mock_embed, mock_pgvector, mock_get_api_key):
        """Test adding empty document list."""
        mock_get_api_key.return_value = "password"
        mock_embed.return_value = []
        
        mock_vectorstore = Mock()
        mock_vectorstore.add_documents = Mock(return_value=[])
        mock_pgvector.return_value = mock_vectorstore

        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )
        store = AsyncPGVectorStore(config, embeddings)

        
        # Mock event loop for run_in_executor
        async def mock_executor(executor, func, *args):
            return func(*args)
        mock_loop = Mock()
        mock_loop.run_in_executor = mock_executor
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            ids = await store.add_documents([])

        assert ids == []

    @pytest.mark.asyncio
    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    @patch('rag.backend.embeddings.embeddings.embed_documents_async')
    async def test_add_documents_with_metadata(self, mock_embed, mock_pgvector, mock_get_api_key):
        """Test that metadata is preserved when adding documents."""
        mock_get_api_key.return_value = "password"
        mock_embed.return_value = [[0.1, 0.2]]
        
        mock_vectorstore = Mock()
        mock_vectorstore.add_documents = Mock(return_value=["doc_1"])
        mock_pgvector.return_value = mock_vectorstore

        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )
        store = AsyncPGVectorStore(config, embeddings)

        metadata = {"source": "test.pdf", "page": 1, "author": "Test"}
        docs = [Document(page_content="Content", metadata=metadata)]
        
        await store.add_documents(docs)

        # Verify add_documents was called with documents containing metadata
        call_args = mock_vectorstore.add_documents.call_args
        added_docs = call_args[0][0]
        assert added_docs[0].metadata == metadata


class TestSimilaritySearch:
    """Test similarity_search method."""

    @pytest.mark.asyncio
    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    @patch('rag.backend.embeddings.embeddings.embed_query_async')
    async def test_similarity_search_basic(self, mock_embed, mock_pgvector, mock_get_api_key):
        """Test basic similarity search."""
        mock_get_api_key.return_value = "password"
        mock_embed.return_value = [0.1, 0.2, 0.3]
        
        result_docs = [
            Document(page_content="Result 1", metadata={}),
            Document(page_content="Result 2", metadata={}),
        ]
        mock_vectorstore = Mock()
        mock_vectorstore.similarity_search = Mock(return_value=result_docs)
        mock_pgvector.return_value = mock_vectorstore

        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )
        store = AsyncPGVectorStore(config, embeddings)

        # Mock event loop for run_in_executor
        async def mock_executor(executor, func, *args):
            return func(*args)
        mock_loop = Mock()
        mock_loop.run_in_executor = mock_executor
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            results = await store.similarity_search("test query", k=2)

        assert len(results) == 2
        assert results[0].page_content == "Result 1"

    @pytest.mark.asyncio
    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    @patch('rag.backend.embeddings.embeddings.embed_query_async')
    async def test_similarity_search_with_k_parameter(self, mock_embed, mock_pgvector, mock_get_api_key):
        """Test similarity search with different k values."""
        mock_get_api_key.return_value = "password"
        mock_embed.return_value = [0.1, 0.2]
        
        mock_vectorstore = Mock()
        mock_vectorstore.similarity_search = Mock(return_value=[Document(page_content="Doc")])
        mock_pgvector.return_value = mock_vectorstore

        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )
        store = AsyncPGVectorStore(config, embeddings)

        # Test with k=10
        # Mock event loop for run_in_executor
        async def mock_executor(executor, func, *args):
            return func(*args)
        mock_loop = Mock()
        mock_loop.run_in_executor = mock_executor
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            await store.similarity_search("query", k=10)
        
        # Verify k parameter was passed
        call_args = mock_vectorstore.similarity_search.call_args
        assert call_args[0][1] == 10  # Second positional arg is k

    @pytest.mark.asyncio
    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    @patch('rag.backend.embeddings.embeddings.embed_query_async')
    async def test_similarity_search_empty_query(self, mock_embed, mock_pgvector, mock_get_api_key):
        """Test similarity search with empty query."""
        mock_get_api_key.return_value = "password"
        mock_embed.return_value = [0.1, 0.2]
        
        mock_vectorstore = Mock()
        mock_vectorstore.similarity_search = Mock(return_value=[])
        mock_pgvector.return_value = mock_vectorstore

        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )
        store = AsyncPGVectorStore(config, embeddings)

        # Mock event loop for run_in_executor
        async def mock_executor(executor, func, *args):
            return func(*args)
        mock_loop = Mock()
        mock_loop.run_in_executor = mock_executor
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            results = await store.similarity_search("", k=5)

        # Should still work, just return empty results
        assert results == []


class TestSimilaritySearchWithScore:
    """Test similarity_search_with_score method."""

    @pytest.mark.asyncio
    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    @patch('rag.backend.embeddings.embeddings.embed_query_async')
    async def test_similarity_search_with_scores(self, mock_embed, mock_pgvector, mock_get_api_key):
        """Test similarity search returns scores."""
        mock_get_api_key.return_value = "password"
        mock_embed.return_value = [0.1, 0.2]
        
        result_with_scores = [
            (Document(page_content="Doc 1"), 0.95),
            (Document(page_content="Doc 2"), 0.87),
        ]
        mock_vectorstore = Mock()
        mock_vectorstore.similarity_search_with_score = Mock(return_value=result_with_scores)
        mock_pgvector.return_value = mock_vectorstore

        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )
        store = AsyncPGVectorStore(config, embeddings)

        # Mock event loop for run_in_executor
        async def mock_executor(executor, func, *args):
            return func(*args)
        mock_loop = Mock()
        mock_loop.run_in_executor = mock_executor
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            results = await store.similarity_search_with_score("query", k=2)

        assert len(results) == 2
        assert results[0][0].page_content == "Doc 1"
        assert results[0][1] == 0.95
        assert results[1][1] == 0.87

    @pytest.mark.asyncio
    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    @patch('rag.backend.embeddings.embeddings.embed_query_async')
    async def test_scores_are_floats(self, mock_embed, mock_pgvector, mock_get_api_key):
        """Test that scores are float type."""
        mock_get_api_key.return_value = "password"
        mock_embed.return_value = [0.1, 0.2]
        
        result_with_scores = [
            (Document(page_content="Doc"), 0.999),
        ]
        mock_vectorstore = Mock()
        mock_vectorstore.similarity_search_with_score = Mock(return_value=result_with_scores)
        mock_pgvector.return_value = mock_vectorstore

        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )
        store = AsyncPGVectorStore(config, embeddings)

        # Mock event loop for run_in_executor
        async def mock_executor(executor, func, *args):
            return func(*args)
        mock_loop = Mock()
        mock_loop.run_in_executor = mock_executor
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            results = await store.similarity_search_with_score("query")

        doc, score = results[0]
        assert isinstance(score, float)


class TestMMRSearch:
    """Test max_marginal_relevance_search method."""

    @pytest.mark.asyncio
    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    @patch('rag.backend.embeddings.embeddings.embed_query_async')
    async def test_mmr_search_basic(self, mock_embed, mock_pgvector, mock_get_api_key):
        """Test MMR search returns diverse results."""
        mock_get_api_key.return_value = "password"
        mock_embed.return_value = [0.1, 0.2]
        
        mmr_results = [
            Document(page_content="Diverse 1"),
            Document(page_content="Diverse 2"),
        ]
        mock_vectorstore = Mock()
        mock_vectorstore.max_marginal_relevance_search = Mock(return_value=mmr_results)
        mock_pgvector.return_value = mock_vectorstore

        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )
        store = AsyncPGVectorStore(config, embeddings)

        results = await store.max_marginal_relevance_search("query", k=2)

        assert len(results) == 2

    @pytest.mark.asyncio
    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    @patch('rag.backend.embeddings.embeddings.embed_query_async')
    async def test_mmr_with_lambda_mult(self, mock_embed, mock_pgvector, mock_get_api_key):
        """Test MMR with different lambda_mult values."""
        mock_get_api_key.return_value = "password"
        mock_embed.return_value = [0.1, 0.2]
        
        mock_vectorstore = Mock()
        mock_vectorstore.max_marginal_relevance_search = Mock(return_value=[])
        mock_pgvector.return_value = mock_vectorstore

        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )
        store = AsyncPGVectorStore(config, embeddings)

        # Test with max diversity (lambda_mult=0)
        await store.max_marginal_relevance_search("query", lambda_mult=0.0)
        
        # Verify lambda_mult was passed
        call_args = mock_vectorstore.max_marginal_relevance_search.call_args
        assert call_args[0][3] == 0.0  # Fourth positional arg is lambda_mult


class TestFactoryFunction:
    """Test create_vectorstore factory function."""

    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    def test_create_vectorstore(self, mock_pgvector, mock_get_api_key):
        """Test factory function creates AsyncPGVectorStore."""
        mock_get_api_key.return_value = "password"
        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )

        store = create_vectorstore(config, embeddings)

        assert isinstance(store, AsyncPGVectorStore)
        assert store.config == config


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    @patch('rag.backend.embeddings.embeddings.embed_documents_async')
    async def test_add_documents_embedding_error(self, mock_embed, mock_pgvector, mock_get_api_key):
        """Test error handling when embedding fails."""
        mock_get_api_key.return_value = "password"
        mock_embed.side_effect = Exception("Embedding API error")

        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )
        store = AsyncPGVectorStore(config, embeddings)

        docs = [Document(page_content="Test")]

        with pytest.raises(Exception, match="Embedding API error"):
            await store.add_documents(docs)

    @pytest.mark.asyncio
    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    @patch('rag.backend.embeddings.embeddings.embed_query_async')
    async def test_search_embedding_error(self, mock_embed, mock_pgvector, mock_get_api_key):
        """Test error handling when query embedding fails."""
        mock_get_api_key.return_value = "password"
        mock_embed.side_effect = Exception("Query embedding failed")

        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )
        store = AsyncPGVectorStore(config, embeddings)

        with pytest.raises(Exception, match="Query embedding failed"):
            # Mock event loop for run_in_executor
            async def mock_executor(executor, func, *args):
                return func(*args)
            mock_loop = Mock()
            mock_loop.run_in_executor = mock_executor
            with patch("asyncio.get_event_loop", return_value=mock_loop):
                await store.similarity_search("query")

    @pytest.mark.asyncio
    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    @patch('rag.backend.embeddings.embeddings.embed_documents_async')
    async def test_very_long_document(self, mock_embed, mock_pgvector, mock_get_api_key):
        """Test adding very long document."""
        mock_get_api_key.return_value = "password"
        mock_embed.return_value = [[0.1] * 1536]
        
        mock_vectorstore = Mock()
        mock_vectorstore.add_documents = Mock(return_value=["doc_1"])
        mock_pgvector.return_value = mock_vectorstore

        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )
        store = AsyncPGVectorStore(config, embeddings)

        # Very long content
        long_content = "Word " * 10000
        docs = [Document(page_content=long_content)]
        
        
        # Mock event loop for run_in_executor
        async def mock_executor(executor, func, *args):
            return func(*args)
        mock_loop = Mock()
        mock_loop.run_in_executor = mock_executor
        with patch("asyncio.get_event_loop", return_value=mock_loop):
            ids = await store.add_documents(docs)
        assert len(ids) == 1

    @pytest.mark.asyncio
    @patch('rag.backend.vectorstore.pgvector_store.get_api_key')
    @patch('rag.backend.vectorstore.pgvector_store.PGVector')
    @patch('rag.backend.embeddings.embeddings.embed_documents_async')
    async def test_unicode_content(self, mock_embed, mock_pgvector, mock_get_api_key):
        """Test adding documents with Unicode content."""
        mock_get_api_key.return_value = "password"
        mock_embed.return_value = [[0.1, 0.2]]
        
        mock_vectorstore = Mock()
        mock_vectorstore.add_documents = Mock(return_value=["doc_1"])
        mock_pgvector.return_value = mock_vectorstore

        embeddings = DummyEmbeddings()
        config = PGVectorConfig(
            host="localhost", port=5432, database="db",
            user="user", password_env="PWD", collection_name="test"
        )
        store = AsyncPGVectorStore(config, embeddings)

        docs = [Document(page_content="Hello 世界 🌍 Привет")]
        ids = await store.add_documents(docs)
        
        assert len(ids) == 1
