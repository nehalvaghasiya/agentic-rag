"""
Comprehensive tests for query route (process_query function).

Tests RAG query processing with boundary and edge cases using mocks.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi import HTTPException

from rag.backend.routes.query import process_query
from rag.backend.schemas import QueryRequest, QueryResponse


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = Mock()
    config.retrieval.search_type = "similarity"
    config.retrieval.k = 4
    config.llm.model = "gpt-3.5-turbo"
    return config


@pytest.fixture
def mock_rag_pipeline():
    """Create mock RAG pipeline."""
    pipeline = AsyncMock()
    pipeline.query = AsyncMock(return_value={
        "answer": "Test answer",
        "query": "What is RAG?",
        "sources": [
            {"content": "Source 1", "metadata": {"page": 1}},
            {"content": "Source 2", "metadata": {"page": 2}},
        ],
    })
    pipeline.get_warnings = Mock(return_value=[])
    return pipeline


class TestProcessQueryBasic:
    """Test basic query processing."""

    @pytest.mark.asyncio
    async def test_successful_query(self, mock_config, mock_rag_pipeline):
        """Test successful query processing."""
        request = QueryRequest(query="What is RAG?")

        result = await process_query(
            request=request,
            rag_pipeline=mock_rag_pipeline,
        )

        assert isinstance(result, QueryResponse)
        assert result.answer == "Test answer"
        assert len(result.sources) == 2
        assert result.sources[0].content == "Source 1"

    @pytest.mark.asyncio
    async def test_pipeline_called_with_query(self, mock_config, mock_rag_pipeline):
        """Test that pipeline is called with correct query."""
        request = QueryRequest(query="Test query")

        await process_query(
            request=request,
            rag_pipeline=mock_rag_pipeline,
        )

        # Verify pipeline.query was called with query
        assert mock_rag_pipeline.query.called
        call_args = mock_rag_pipeline.query.call_args
        assert call_args[0][0] == "Test query"  # First positional arg

    @pytest.mark.asyncio
    async def test_query_with_warnings(self, mock_config):
        """Test query returns warnings from RAG pipeline."""
        pipeline = AsyncMock()
        pipeline.query = AsyncMock(return_value={
            "answer": "Answer",
            "query": "Test",
            "sources": [],
        })
        pipeline.get_warnings = Mock(return_value=["Using dummy LLM"])

        request = QueryRequest(query="Test")

        result = await process_query(
            request=request,
            rag_pipeline=pipeline,
        )

        assert result.warnings == ["Using dummy LLM"]


class TestQueryValidation:
    """Test query validation."""

    @pytest.mark.asyncio
    async def test_empty_query_string(self, mock_config, mock_rag_pipeline):
        """Test handling empty query string."""
        # Empty string should raise validation error due to min_length=1
        with pytest.raises(Exception):  # ValidationError from pydantic
            request = QueryRequest(query="")

    @pytest.mark.asyncio
    async def test_whitespace_only_query(self, mock_config, mock_rag_pipeline):
        """Test handling whitespace-only query."""
        request = QueryRequest(query="   \n\t   ")

        result = await process_query(
            request=request,
            rag_pipeline=mock_rag_pipeline,
        )

        assert isinstance(result, QueryResponse)

    @pytest.mark.asyncio
    async def test_very_long_query(self, mock_config, mock_rag_pipeline):
        """Test handling very long query (1000+ characters)."""
        long_query = "What is " + " and ".join(["question"] * 200) + "?"
        request = QueryRequest(query=long_query)

        result = await process_query(
            request=request,
            rag_pipeline=mock_rag_pipeline,
        )

        assert isinstance(result, QueryResponse)
        # Verify long query was passed to pipeline
        call_args = mock_rag_pipeline.query.call_args
        assert len(call_args[0][0]) > 1000


class TestSourceHandling:
    """Test handling of source documents."""

    @pytest.mark.asyncio
    async def test_no_sources_returned(self, mock_config):
        """Test handling when pipeline returns no sources."""
        pipeline = AsyncMock()
        pipeline.query = AsyncMock(return_value={
            "answer": "No relevant sources found.",
            "query": "Test",
            "sources": [],
        })
        pipeline.get_warnings = Mock(return_value=[])

        request = QueryRequest(query="Test")

        result = await process_query(
            request=request,
            rag_pipeline=pipeline,
        )

        assert result.sources == []

    @pytest.mark.asyncio
    async def test_single_source(self, mock_config):
        """Test handling single source document."""
        pipeline = AsyncMock()
        pipeline.query = AsyncMock(return_value={
            "answer": "Answer based on one source.",
            "query": "Test",
            "sources": [{"content": "Only source", "metadata": {}}],
        })
        pipeline.get_warnings = Mock(return_value=[])

        request = QueryRequest(query="Test")

        result = await process_query(
            request=request,
            rag_pipeline=pipeline,
        )

        assert len(result.sources) == 1

    @pytest.mark.asyncio
    async def test_many_sources(self, mock_config):
        """Test handling many source documents."""
        pipeline = AsyncMock()
        sources = [
            {"content": f"Source {i}", "metadata": {"index": i}}
            for i in range(20)
        ]
        pipeline.query = AsyncMock(return_value={
            "answer": "Answer from many sources.",
            "query": "Test",
            "sources": sources,
        })
        pipeline.get_warnings = Mock(return_value=[])

        request = QueryRequest(query="Test")

        result = await process_query(
            request=request,
            rag_pipeline=pipeline,
        )

        assert len(result.sources) == 20


class TestSourceMetadata:
    """Test source metadata handling."""

    @pytest.mark.asyncio
    async def test_sources_with_metadata(self, mock_config):
        """Test that source metadata is preserved."""
        pipeline = AsyncMock()
        pipeline.query = AsyncMock(return_value={
            "answer": "Answer",
            "query": "Test",
            "sources": [
                {
                    "content": "Source",
                    "metadata": {
                        "page": 42,
                        "source": "document.pdf",
                        "author": "Test Author",
                    }
                }
            ],
        })
        pipeline.get_warnings = Mock(return_value=[])

        request = QueryRequest(query="Test")

        result = await process_query(
            request=request,
            rag_pipeline=pipeline,
        )

        assert result.sources[0].metadata["page"] == 42
        assert result.sources[0].metadata["author"] == "Test Author"

    @pytest.mark.asyncio
    async def test_sources_without_metadata(self, mock_config):
        """Test sources with empty metadata."""
        pipeline = AsyncMock()
        pipeline.query = AsyncMock(return_value={
            "answer": "Answer",
            "query": "Test",
            "sources": [{"content": "Source", "metadata": {}}],
        })
        pipeline.get_warnings = Mock(return_value=[])

        request = QueryRequest(query="Test")

        result = await process_query(
            request=request,
            rag_pipeline=pipeline,
        )

        assert result.sources[0].metadata == {}


class TestErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_pipeline_error_raises_http_exception(self, mock_config):
        """Test that pipeline errors raise HTTPException."""
        pipeline = AsyncMock()
        pipeline.query = AsyncMock(side_effect=Exception("Pipeline error"))
        pipeline.get_warnings = Mock(return_value=[])

        request = QueryRequest(query="Test")

        with pytest.raises(HTTPException) as exc_info:
            await process_query(
            request=request,
            rag_pipeline=pipeline,
        )

        assert exc_info.value.status_code == 500
        assert "Pipeline error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_embedding_error_propagates(self, mock_config):
        """Test that embedding errors are caught and converted."""
        pipeline = AsyncMock()
        pipeline.query = AsyncMock(side_effect=Exception("Embedding failed"))
        pipeline.get_warnings = Mock(return_value=[])

        request = QueryRequest(query="Test")

        with pytest.raises(HTTPException):
            await process_query(
            request=request,
            rag_pipeline=pipeline,
        )

    @pytest.mark.asyncio
    async def test_llm_error_propagates(self, mock_config):
        """Test that LLM errors are caught and converted."""
        pipeline = AsyncMock()
        pipeline.query = AsyncMock(side_effect=Exception("LLM generation failed"))
        pipeline.get_warnings = Mock(return_value=[])

        request = QueryRequest(query="Test")

        with pytest.raises(HTTPException):
            await process_query(
            request=request,
            rag_pipeline=pipeline,
        )


class TestUnicodeHandling:
    """Test Unicode and special character handling."""

    @pytest.mark.asyncio
    async def test_unicode_query(self, mock_config, mock_rag_pipeline):
        """Test query with Unicode characters."""
        request = QueryRequest(query="什么是RAG？")  # Chinese

        result = await process_query(
            request=request,
            rag_pipeline=mock_rag_pipeline,
        )

        assert isinstance(result, QueryResponse)
        # Verify Unicode was passed to pipeline
        call_args = mock_rag_pipeline.query.call_args
        assert "什么是RAG？" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_emoji_in_query(self, mock_config, mock_rag_pipeline):
        """Test query containing emoji."""
        request = QueryRequest(query="What is RAG? 🤖📚")

        result = await process_query(
            request=request,
            rag_pipeline=mock_rag_pipeline,
        )

        assert isinstance(result, QueryResponse)

    @pytest.mark.asyncio
    async def test_special_characters(self, mock_config, mock_rag_pipeline):
        """Test query with special characters."""
        request = QueryRequest(query="What is <RAG> & how does it work?")

        result = await process_query(
            request=request,
            rag_pipeline=mock_rag_pipeline,
        )

        assert isinstance(result, QueryResponse)


class TestPipelineIntegration:
    """Test RAG pipeline integration."""

    @pytest.mark.asyncio
    async def test_pipeline_returns_complete_response(self, mock_config):
        """Test that pipeline returns all expected fields."""
        pipeline = AsyncMock()
        pipeline.query = AsyncMock(return_value={
            "answer": "Complete answer with context.",
            "query": "Test",
            "sources": [
                {"content": "Source 1", "metadata": {"page": 1}},
                {"content": "Source 2", "metadata": {"page": 2}},
            ],
        })
        pipeline.get_warnings = Mock(return_value=["Warning 1", "Warning 2"])

        request = QueryRequest(query="Test")

        result = await process_query(
            request=request,
            rag_pipeline=pipeline,
        )

        # Verify all fields are populated
        assert result.answer
        assert len(result.sources) == 2
        assert len(result.warnings) == 2

    @pytest.mark.asyncio
    async def test_pipeline_called_once(self, mock_config, mock_rag_pipeline):
        """Test that pipeline.run is called exactly once."""
        request = QueryRequest(query="Test")

        await process_query(
            request=request,
            rag_pipeline=mock_rag_pipeline,
        )

        assert mock_rag_pipeline.query.call_count == 1


class TestEdgeCases:
    """Test edge cases."""

    @pytest.mark.asyncio
    async def test_answer_with_newlines(self, mock_config):
        """Test answer containing newlines and formatting."""
        pipeline = AsyncMock()
        pipeline.query = AsyncMock(return_value={
            "answer": "Line 1\n\nLine 2\n\nLine 3",
            "query": "Test",
            "sources": [],
        })
        pipeline.get_warnings = Mock(return_value=[])

        request = QueryRequest(query="Test")

        result = await process_query(
            request=request,
            rag_pipeline=pipeline,
        )

        assert "\n" in result.answer

    @pytest.mark.asyncio
    async def test_answer_with_code_blocks(self, mock_config):
        """Test answer containing code blocks."""
        pipeline = AsyncMock()
        pipeline.query = AsyncMock(return_value={
            "answer": "Here's code:\n```python\nprint('hello')\n```",
            "query": "Test",
            "sources": [],
        })
        pipeline.get_warnings = Mock(return_value=[])

        request = QueryRequest(query="Test")

        result = await process_query(
            request=request,
            rag_pipeline=pipeline,
        )

        assert "```" in result.answer

    @pytest.mark.asyncio
    async def test_source_content_very_long(self, mock_config):
        """Test source with very long content."""
        pipeline = AsyncMock()
        long_content = "word " * 10000  # Very long source
        pipeline.query = AsyncMock(return_value={
            "answer": "Answer",
            "query": "Test",
            "sources": [{"content": long_content, "metadata": {}}],
        })
        pipeline.get_warnings = Mock(return_value=[])

        request = QueryRequest(query="Test")

        result = await process_query(
            request=request,
            rag_pipeline=pipeline,
        )

        assert len(result.sources[0].content) >= 50000

    @pytest.mark.asyncio
    async def test_multiple_queries_independent(self, mock_config, mock_rag_pipeline):
        """Test that multiple queries are processed independently."""
        request1 = QueryRequest(query="Query 1")
        request2 = QueryRequest(query="Query 2")

        result1 = await process_query(
            request=request1,
            rag_pipeline=mock_rag_pipeline,
        )
        result2 = await process_query(
            request=request2,
            rag_pipeline=mock_rag_pipeline,
        )

        # Both should succeed independently
        assert isinstance(result1, QueryResponse)
        assert isinstance(result2, QueryResponse)


class TestQueryRequestFields:
    """Test QueryRequest field handling."""

    @pytest.mark.asyncio
    async def test_query_field_required(self, mock_config, mock_rag_pipeline):
        """Test that query field is properly used."""
        request = QueryRequest(query="Required query text")

        result = await process_query(
            request=request,
            rag_pipeline=mock_rag_pipeline,
        )

        # Verify query was extracted and used
        call_args = mock_rag_pipeline.query.call_args
        assert call_args[0][0] == "Required query text"


class TestResponseConstruction:
    """Test QueryResponse construction."""

    @pytest.mark.asyncio
    async def test_response_structure(self, mock_config):
        """Test that response has correct structure."""
        pipeline = AsyncMock()
        pipeline.query = AsyncMock(return_value={
            "answer": "Test answer",
            "query": "Test",
            "sources": [{"content": "Source", "metadata": {"key": "value"}}],
        })
        pipeline.get_warnings = Mock(return_value=["Warning"])

        request = QueryRequest(query="Test")

        result = await process_query(
            request=request,
            rag_pipeline=pipeline,
        )

        # Verify all QueryResponse fields
        assert hasattr(result, "answer")
        assert hasattr(result, "sources")
        assert hasattr(result, "warnings")
        assert isinstance(result.sources, list)
        assert isinstance(result.warnings, list)
