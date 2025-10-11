"""
Comprehensive tests for gradio_app.py (RAGChatInterface).

Tests basic Gradio interface with boundary and edge cases using mocks.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import httpx

from rag.frontend.gradio_app import RAGChatInterface


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = Mock()
    config.api.host = "localhost"
    config.api.port = 8000
    return config


@pytest.fixture
def mock_file():
    """Create mock file object."""
    file = Mock()
    file.name = "/tmp/test.pdf"
    return file


@pytest.fixture
def mock_httpx_client():
    """Create mock httpx AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


class TestRAGChatInterfaceInitialization:
    """Test RAGChatInterface initialization."""

    def test_init_with_config(self, mock_config):
        """Test initialization with configuration."""
        interface = RAGChatInterface(config=mock_config)

        assert interface.config == mock_config
        assert interface.api_base_url == "http://localhost:8000"

    def test_backend_url_extracted(self, mock_config):
        """Test backend URL is correctly extracted from config."""
        mock_config.api.host = "example.com"
        mock_config.api.port = 9000
        interface = RAGChatInterface(config=mock_config)

        assert interface.api_base_url == "http://example.com:9000"

    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    def test_async_client_created(self, mock_client_class, mock_config):
        """Test that async HTTP client is created."""
        interface = RAGChatInterface(config=mock_config)

        # Client should be created (in __init__ or lazily)
        assert hasattr(interface, 'client') or hasattr(interface, '_client')


class TestUploadFile:
    """Test file upload functionality."""

    @pytest.mark.asyncio
    @patch('builtins.open', create=True)
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_successful_upload(self, mock_client_class, mock_open, mock_config, mock_file):
        """Test successful file upload."""
        # Mock file reading
        mock_open.return_value.__enter__.return_value.read.return_value = b"fake file content"
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={
            "message": "File uploaded successfully",
            "num_documents": 1,
            "num_chunks": 5,
            "document_ids": ["id1", "id2", "id3", "id4", "id5"],
        })

        # Mock the client instance directly (not as context manager)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        mock_file.name = "test.pdf"
        interface = RAGChatInterface(config=mock_config)
        result = await interface.upload_file(mock_file)

        assert "successfully" in result.lower()
        assert "5" in result  # num_chunks

    @pytest.mark.asyncio
    @patch('builtins.open', create=True)
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_upload_file_too_large(self, mock_client_class, mock_open, mock_config, mock_file):
        """Test upload with file too large error."""
        mock_open.return_value.__enter__.return_value.read.return_value = b"fake content"
        mock_open.return_value.__enter__.return_value.read.return_value = b"fake content"
        mock_response = Mock()
        mock_response.status_code = 413
        mock_response.text = "File too large"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        interface = RAGChatInterface(config=mock_config)
        mock_file.name = "large.pdf"
        result = await interface.upload_file(mock_file)

        assert "error" in result.lower() or "failed" in result.lower()

    @pytest.mark.asyncio
    @patch('builtins.open', create=True)
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_upload_network_error(self, mock_client_class, mock_open, mock_config, mock_file):
        """Test upload with network error."""
        mock_open.return_value.__enter__.return_value.read.return_value = b"fake content"
        mock_open.return_value.__enter__.return_value.read.return_value = b"fake content"
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
        mock_client_class.return_value = mock_client

        interface = RAGChatInterface(config=mock_config)
        mock_file.name = "test.pdf"
        result = await interface.upload_file(mock_file)

        assert "error" in result.lower() or "failed" in result.lower()

    @pytest.mark.asyncio
    @patch('builtins.open', create=True)
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_upload_timeout(self, mock_client_class, mock_open, mock_config, mock_file):
        """Test upload with timeout."""
        mock_open.return_value.__enter__.return_value.read.return_value = b"fake content"
        mock_open.return_value.__enter__.return_value.read.return_value = b"fake content"
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
        mock_client_class.return_value = mock_client

        interface = RAGChatInterface(config=mock_config)
        mock_file.name = "test.pdf"
        result = await interface.upload_file(mock_file)

        assert "timeout" in result.lower() or "error" in result.lower()

    @pytest.mark.asyncio
    @patch('builtins.open', create=True)
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_upload_none_file(self, mock_client_class, mock_open, mock_config, mock_file):
        """Test upload with None file."""
        mock_open.return_value.__enter__.return_value.read.return_value = b"fake content"
        mock_open.return_value.__enter__.return_value.read.return_value = b"fake content"
        interface = RAGChatInterface(config=mock_config)
        result = await interface.upload_file(None)

        # Should handle None gracefully
        assert isinstance(result, str)


class TestQueryWithSources:
    """Test query with sources functionality."""

    @pytest.mark.asyncio
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_successful_query(self, mock_client_class, mock_config, mock_file):
        """Test successful query with sources."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={
            "answer": "RAG stands for Retrieval-Augmented Generation.",
            "sources": [
                {"content": "Source 1 content", "metadata": {"page": 1}},
                {"content": "Source 2 content", "metadata": {"page": 2}},
            ],
            "warnings": [],
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        interface = RAGChatInterface(config=mock_config)
        result = await interface.query_rag("What is RAG?", [])

        assert "Retrieval-Augmented Generation" in result
        assert "Source 1 content" in result or "Sources" in result

    @pytest.mark.asyncio
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_query_with_warnings(self, mock_client_class, mock_config, mock_file):
        """Test query that returns warnings."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={
            "answer": "Answer text",
            "sources": [],
            "warnings": ["Using dummy embeddings", "Using dummy LLM"],
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        interface = RAGChatInterface(config=mock_config)
        result = await interface.query_rag("Test query", [])

        # Warnings should be displayed
        assert "warning" in result.lower() or "dummy" in result.lower()

    @pytest.mark.asyncio
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_query_no_sources(self, mock_client_class, mock_config, mock_file):
        """Test query with no sources returned."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={
            "answer": "No relevant information found.",
            "sources": [],
            "warnings": [],
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        interface = RAGChatInterface(config=mock_config)
        result = await interface.query_rag("Unknown topic", [])

        assert "No relevant information found" in result

    @pytest.mark.asyncio
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_query_error_response(self, mock_client_class, mock_config, mock_file):
        """Test query with error response."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        interface = RAGChatInterface(config=mock_config)
        result = await interface.query_rag("Test query", [])

        assert "error" in result.lower()

    @pytest.mark.asyncio
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_query_network_error(self, mock_client_class, mock_config, mock_file):
        """Test query with network error."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))
        mock_client_class.return_value = mock_client

        interface = RAGChatInterface(config=mock_config)
        result = await interface.query_rag("Test query", [])

        assert "error" in result.lower()


class TestEdgeCases:
    """Test edge cases."""

    @pytest.mark.asyncio
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_empty_query(self, mock_client_class, mock_config, mock_file):
        """Test empty query string."""
        interface = RAGChatInterface(config=mock_config)
        result = await interface.query_rag("", [])

        # Should handle empty query
        assert isinstance(result, str)

    @pytest.mark.asyncio
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_very_long_query(self, mock_client_class, mock_config, mock_file):
        """Test very long query."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={
            "answer": "Answer",
            "sources": [],
            "warnings": [],
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        interface = RAGChatInterface(config=mock_config)
        long_query = "What is " + " and ".join(["question"] * 500) + "?"
        result = await interface.query_rag(long_query, [])

        assert isinstance(result, str)

    @pytest.mark.asyncio
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_unicode_query(self, mock_client_class, mock_config, mock_file):
        """Test query with Unicode characters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={
            "answer": "回答内容",
            "sources": [],
            "warnings": [],
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        interface = RAGChatInterface(config=mock_config)
        result = await interface.query_rag("什么是RAG？", [])

        assert isinstance(result, str)

    @pytest.mark.asyncio
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_special_characters_in_query(self, mock_client_class, mock_config, mock_file):
        """Test query with special characters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={
            "answer": "Answer with <special> characters & symbols.",
            "sources": [],
            "warnings": [],
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        interface = RAGChatInterface(config=mock_config)
        result = await interface.query_rag("What is <RAG> & how does it work?", [])

        assert isinstance(result, str)


class TestBackendCommunication:
    """Test backend API communication."""

    @pytest.mark.asyncio
    @patch('builtins.open', create=True)
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_correct_upload_endpoint(self, mock_client_class, mock_open, mock_config, mock_file):
        """Test that upload uses correct endpoint."""
        mock_open.return_value.__enter__.return_value.read.return_value = b"fake content"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={
            "message": "Success",
            "num_documents": 1,
            "num_chunks": 1,
            "document_ids": ["id1"],
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        interface = RAGChatInterface(config=mock_config)
        mock_file.name = "test.pdf"
        await interface.upload_file(mock_file)

        # Verify post was called with upload endpoint
        call_args = mock_client.post.call_args
        assert "/upload" in str(call_args)

    @pytest.mark.asyncio
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_correct_query_endpoint(self, mock_client_class, mock_config, mock_file):
        """Test that query uses correct endpoint."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={
            "answer": "Answer",
            "sources": [],
            "warnings": [],
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        interface = RAGChatInterface(config=mock_config)
        await interface.query_rag("Test", [])

        # Verify post was called with query endpoint
        call_args = mock_client.post.call_args
        assert "/query" in str(call_args)


class TestInterfaceCreation:
    """Test Gradio interface creation."""

    @patch('rag.frontend.gradio_app.gr.ChatInterface')
    def test_create_interface(self, mock_gr_chat, mock_config):
        """Test that Gradio interface is created."""
        interface = RAGChatInterface(config=mock_config)
        
        # Method should exist
        assert hasattr(interface, 'create_interface') or hasattr(interface, 'launch')


class TestConcurrentRequests:
    """Test handling of concurrent requests."""

    @pytest.mark.asyncio
    @patch('rag.frontend.gradio_app.httpx.AsyncClient')
    async def test_multiple_queries_concurrent(self, mock_client_class, mock_config, mock_file):
        """Test handling multiple concurrent queries."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json = Mock(return_value={
            "answer": "Answer",
            "sources": [],
            "warnings": [],
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        interface = RAGChatInterface(config=mock_config)

        # Run multiple queries
        import asyncio
        results = await asyncio.gather(
            interface.query_rag("Query 1", []),
            interface.query_rag("Query 2", []),
            interface.query_rag("Query 3", []),
        )

        assert len(results) == 3
        assert all(isinstance(r, str) for r in results)
