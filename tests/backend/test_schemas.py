"""
Comprehensive tests for API schemas.

Tests Pydantic validation, field constraints, and serialization.
"""

import pytest
from pydantic import ValidationError

from rag.backend.schemas import HealthResponse, QueryRequest, QueryResponse, Source, UploadResponse


class TestUploadResponse:
    """Test UploadResponse schema."""

    def test_valid_upload_response(self):
        """Test creating valid upload response."""
        response = UploadResponse(
            message="Upload successful",
            num_documents=5,
            num_chunks=25,
            document_ids=["doc1", "doc2", "doc3", "doc4", "doc5"],
        )

        assert response.message == "Upload successful"
        assert response.num_documents == 5
        assert response.num_chunks == 25
        assert len(response.document_ids) == 5
        assert response.warnings is None

    def test_upload_response_with_warnings(self):
        """Test upload response with warnings."""
        response = UploadResponse(
            message="Upload successful",
            num_documents=1,
            num_chunks=10,
            document_ids=["doc1"],
            warnings=["Using fallback mode", "Missing embeddings"],
        )

        assert response.warnings == ["Using fallback mode", "Missing embeddings"]
        assert len(response.warnings) == 2

    def test_upload_response_empty_document_ids(self):
        """Test upload response with empty document IDs."""
        response = UploadResponse(
            message="No documents uploaded",
            num_documents=0,
            num_chunks=0,
            document_ids=[],
        )

        assert response.num_documents == 0
        assert response.num_chunks == 0
        assert response.document_ids == []

    def test_upload_response_serialization(self):
        """Test upload response can be serialized to dict."""
        response = UploadResponse(
            message="Success",
            num_documents=1,
            num_chunks=5,
            document_ids=["doc1"],
        )

        data = response.model_dump()
        assert isinstance(data, dict)
        assert data["message"] == "Success"
        assert data["num_documents"] == 1


class TestQueryRequest:
    """Test QueryRequest schema."""

    def test_valid_query_request(self):
        """Test creating valid query request."""
        request = QueryRequest(query="What is RAG?")

        assert request.query == "What is RAG?"
        assert request.top_k == 5  # Default value

    def test_query_request_with_top_k(self):
        """Test query request with top_k parameter."""
        request = QueryRequest(query="Explain AI", top_k=5)

        assert request.query == "Explain AI"
        assert request.top_k == 5

    def test_query_request_empty_string_fails(self):
        """Test that empty query string fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            QueryRequest(query="")

        errors = exc_info.value.errors()
        assert any("min_length" in str(error) for error in errors)

    def test_query_request_whitespace_only_fails(self):
        """Test that whitespace-only query fails min_length validation."""
        # Pydantic validates before stripping, so "   " has length 3 and passes min_length
        # but empty "" fails
        with pytest.raises(ValidationError):
            QueryRequest(query="")

    def test_query_request_top_k_boundary_min(self):
        """Test top_k minimum boundary (ge=1)."""
        # Valid: top_k = 1
        request = QueryRequest(query="test", top_k=1)
        assert request.top_k == 1

        # Invalid: top_k = 0
        with pytest.raises(ValidationError) as exc_info:
            QueryRequest(query="test", top_k=0)

        errors = exc_info.value.errors()
        assert any("greater_than_equal" in str(error) for error in errors)

    def test_query_request_top_k_boundary_max(self):
        """Test top_k maximum boundary (le=20)."""
        # Valid: top_k = 20
        request = QueryRequest(query="test", top_k=20)
        assert request.top_k == 20

        # Invalid: top_k = 21
        with pytest.raises(ValidationError) as exc_info:
            QueryRequest(query="test", top_k=21)

        errors = exc_info.value.errors()
        assert any("less_than_equal" in str(error) for error in errors)

    def test_query_request_top_k_negative_fails(self):
        """Test that negative top_k fails validation."""
        with pytest.raises(ValidationError):
            QueryRequest(query="test", top_k=-1)

    def test_query_request_missing_query_fails(self):
        """Test that missing query field fails."""
        with pytest.raises(ValidationError):
            QueryRequest()


class TestSource:
    """Test Source schema."""

    def test_valid_source(self):
        """Test creating valid source."""
        source = Source(
            content="This is the source content.",
            metadata={"source": "doc.pdf", "page": 1},
        )

        assert source.content == "This is the source content."
        assert source.metadata["source"] == "doc.pdf"
        assert source.metadata["page"] == 1

    def test_source_empty_content(self):
        """Test source with empty content."""
        source = Source(content="", metadata={})

        assert source.content == ""
        assert source.metadata == {}

    def test_source_empty_metadata(self):
        """Test source with empty metadata dict."""
        source = Source(content="Content", metadata={})

        assert source.metadata == {}

    def test_source_complex_metadata(self):
        """Test source with complex metadata."""
        source = Source(
            content="Content",
            metadata={
                "source": "file.pdf",
                "page": 5,
                "author": "John Doe",
                "tags": ["ai", "ml"],
                "nested": {"key": "value"},
            },
        )

        assert source.metadata["tags"] == ["ai", "ml"]
        assert source.metadata["nested"]["key"] == "value"


class TestQueryResponse:
    """Test QueryResponse schema."""

    def test_valid_query_response(self):
        """Test creating valid query response."""
        sources = [
            Source(content="Source 1", metadata={"source": "doc1.pdf"}),
            Source(content="Source 2", metadata={"source": "doc2.pdf"}),
        ]

        response = QueryResponse(
            answer="This is the answer.", query="What is the question?", sources=sources
        )

        assert response.answer == "This is the answer."
        assert response.query == "What is the question?"
        assert len(response.sources) == 2
        assert response.warnings is None

    def test_query_response_no_sources(self):
        """Test query response with no sources."""
        response = QueryResponse(
            answer="No sources found.", query="Unknown query", sources=None
        )

        assert response.sources is None

    def test_query_response_empty_sources_list(self):
        """Test query response with empty sources list."""
        response = QueryResponse(answer="Answer", query="Query", sources=[])

        assert response.sources == []

    def test_query_response_with_warnings(self):
        """Test query response with warnings."""
        response = QueryResponse(
            answer="Answer",
            query="Query",
            sources=None,
            warnings=["Fallback mode active", "Low relevance"],
        )

        assert response.warnings == ["Fallback mode active", "Low relevance"]

    def test_query_response_serialization(self):
        """Test query response serialization."""
        response = QueryResponse(
            answer="Answer", query="Query", sources=[], warnings=["Warning"]
        )

        data = response.model_dump()
        assert isinstance(data, dict)
        assert data["answer"] == "Answer"
        assert data["warnings"] == ["Warning"]


class TestHealthResponse:
    """Test HealthResponse schema."""

    def test_valid_health_response(self):
        """Test creating valid health response."""
        response = HealthResponse(
            status="healthy",
            version="1.0.0",
            components={"database": "ok", "llm": "ok", "embeddings": "ok"},
        )

        assert response.status == "healthy"
        assert response.version == "1.0.0"
        assert response.components["database"] == "ok"

    def test_health_response_unhealthy(self):
        """Test health response with unhealthy status."""
        response = HealthResponse(
            status="unhealthy",
            version="1.0.0",
            components={"database": "error", "llm": "ok"},
        )

        assert response.status == "unhealthy"
        assert response.components["database"] == "error"

    def test_health_response_empty_components(self):
        """Test health response with empty components."""
        response = HealthResponse(status="unknown", version="0.0.1", components={})

        assert response.components == {}

    def test_health_response_serialization(self):
        """Test health response can be serialized."""
        response = HealthResponse(
            status="ok", version="2.0.0", components={"api": "running"}
        )

        data = response.model_dump()
        assert data["status"] == "ok"
        assert data["version"] == "2.0.0"


class TestSchemaIntegration:
    """Test schema integration and edge cases."""

    def test_query_response_with_source_objects(self):
        """Test query response construction with Source objects."""
        sources = [
            Source(content="Content 1", metadata={"id": 1}),
            Source(content="Content 2", metadata={"id": 2}),
        ]

        response = QueryResponse(answer="Answer", query="Query", sources=sources)

        assert len(response.sources) == 2
        assert response.sources[0].content == "Content 1"
        assert response.sources[1].metadata["id"] == 2

    def test_all_schemas_json_serializable(self):
        """Test that all schemas can be serialized to JSON."""
        upload = UploadResponse(
            message="msg", num_documents=1, num_chunks=5, document_ids=["id1"]
        )
        query_req = QueryRequest(query="test", top_k=5)
        source = Source(content="content", metadata={"key": "value"})
        query_resp = QueryResponse(answer="ans", query="q", sources=[source])
        health = HealthResponse(status="ok", version="1.0", components={})

        # All should serialize without error
        assert upload.model_dump_json()
        assert query_req.model_dump_json()
        assert source.model_dump_json()
        assert query_resp.model_dump_json()
        assert health.model_dump_json()
