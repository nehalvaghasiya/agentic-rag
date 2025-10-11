"""
Comprehensive tests for upload route (process_upload function).

Tests file upload processing with boundary and edge cases using mocks.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from pathlib import Path
from fastapi import UploadFile, HTTPException
from io import BytesIO
from langchain_core.documents import Document

from rag.backend.routes.upload import process_upload
from rag.backend.schemas import UploadResponse


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = Mock()
    config.app.max_upload_size_mb = 5
    config.preprocessing.enabled = True
    config.preprocessing.cleaning = True
    return config


@pytest.fixture
def mock_loader_factory():
    """Create mock loader factory."""
    factory = Mock()
    loader = AsyncMock()
    loader.load = AsyncMock(return_value=[
        Document(page_content="Test content", metadata={"source": "test"})
    ])
    factory.get_loader = Mock(return_value=loader)
    return factory


@pytest.fixture
def mock_text_cleaner():
    """Create mock text cleaner."""
    cleaner = Mock()
    cleaner.process = Mock(side_effect=lambda docs: docs)  # Pass through
    return cleaner


@pytest.fixture
def mock_text_splitter():
    """Create mock text splitter."""
    splitter = Mock()
    splitter.split_documents = Mock(return_value=[
        Document(page_content="Chunk 1", metadata={}),
        Document(page_content="Chunk 2", metadata={}),
    ])
    return splitter


@pytest.fixture
def mock_vectorstore():
    """Create mock vectorstore."""
    store = AsyncMock()
    store.add_documents = AsyncMock(return_value=["id1", "id2"])
    return store


class TestProcessUploadBasic:
    """Test basic upload processing."""

    @pytest.mark.asyncio
    async def test_successful_upload(
        self, mock_config, mock_loader_factory, mock_text_cleaner,
        mock_text_splitter, mock_vectorstore
    ):
        """Test successful file upload and processing."""
        # Create mock UploadFile
        file_content = b"Test file content"
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.read = AsyncMock(return_value=file_content)

        result = await process_upload(
            file=mock_file,
            config=mock_config,
            loader_factory=mock_loader_factory,
            text_cleaner=mock_text_cleaner,
            text_splitter=mock_text_splitter,
            vectorstore=mock_vectorstore,
        )

        assert isinstance(result, UploadResponse)
        assert result.num_documents == 1
        assert result.num_chunks == 2
        assert len(result.document_ids) == 2
        assert "test.txt" in result.message

    @pytest.mark.asyncio
    async def test_upload_with_warnings(
        self, mock_config, mock_loader_factory, mock_text_cleaner,
        mock_text_splitter, mock_vectorstore
    ):
        """Test upload returns warnings from RAG pipeline."""
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.pdf"
        mock_file.read = AsyncMock(return_value=b"content")

        # Mock RAG pipeline with warnings
        mock_rag_pipeline = Mock()
        mock_rag_pipeline.get_warnings = Mock(return_value=["Using dummy embeddings"])

        result = await process_upload(
            file=mock_file,
            config=mock_config,
            loader_factory=mock_loader_factory,
            text_cleaner=mock_text_cleaner,
            text_splitter=mock_text_splitter,
            vectorstore=mock_vectorstore,
            rag_pipeline=mock_rag_pipeline,
        )

        assert result.warnings == ["Using dummy embeddings"]


class TestFileSizeValidation:
    """Test file size validation."""

    @pytest.mark.asyncio
    async def test_file_too_large_raises_error(
        self, mock_config, mock_loader_factory, mock_text_cleaner,
        mock_text_splitter, mock_vectorstore
    ):
        """Test that files exceeding max size raise HTTPException."""
        # Create file larger than max_upload_size_mb (5MB)
        large_content = b"x" * (6 * 1024 * 1024)  # 6 MB
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "large.pdf"
        mock_file.read = AsyncMock(return_value=large_content)

        with pytest.raises(HTTPException) as exc_info:
            await process_upload(
                file=mock_file,
                config=mock_config,
                loader_factory=mock_loader_factory,
                text_cleaner=mock_text_cleaner,
                text_splitter=mock_text_splitter,
                vectorstore=mock_vectorstore,
            )

        assert exc_info.value.status_code == 413
        assert "too large" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_exact_max_size_allowed(
        self, mock_config, mock_loader_factory, mock_text_cleaner,
        mock_text_splitter, mock_vectorstore
    ):
        """Test that file at exact max size is allowed."""
        # Create file exactly at max size (5MB)
        exact_size_content = b"x" * (5 * 1024 * 1024)
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "exact.pdf"
        mock_file.read = AsyncMock(return_value=exact_size_content)

        result = await process_upload(
            file=mock_file,
            config=mock_config,
            loader_factory=mock_loader_factory,
            text_cleaner=mock_text_cleaner,
            text_splitter=mock_text_splitter,
            vectorstore=mock_vectorstore,
        )

        assert isinstance(result, UploadResponse)

    @pytest.mark.asyncio
    async def test_empty_file(
        self, mock_config, mock_loader_factory, mock_text_cleaner,
        mock_text_splitter, mock_vectorstore
    ):
        """Test uploading empty file."""
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "empty.txt"
        mock_file.read = AsyncMock(return_value=b"")

        # Empty file should be processed (loader may handle it)
        result = await process_upload(
            file=mock_file,
            config=mock_config,
            loader_factory=mock_loader_factory,
            text_cleaner=mock_text_cleaner,
            text_splitter=mock_text_splitter,
            vectorstore=mock_vectorstore,
        )

        assert isinstance(result, UploadResponse)


class TestDocumentLoading:
    """Test document loading step."""

    @pytest.mark.asyncio
    async def test_loader_called_with_temp_file(
        self, mock_config, mock_loader_factory, mock_text_cleaner,
        mock_text_splitter, mock_vectorstore
    ):
        """Test that loader is called with temporary file path."""
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.pdf"
        mock_file.read = AsyncMock(return_value=b"content")

        await process_upload(
            file=mock_file,
            config=mock_config,
            loader_factory=mock_loader_factory,
            text_cleaner=mock_text_cleaner,
            text_splitter=mock_text_splitter,
            vectorstore=mock_vectorstore,
        )

        # Verify loader was obtained and used
        assert mock_loader_factory.get_loader.called
        loader = mock_loader_factory.get_loader.return_value
        assert loader.load.called

    @pytest.mark.asyncio
    async def test_multiple_documents_from_loader(
        self, mock_config, mock_text_cleaner, mock_text_splitter, mock_vectorstore
    ):
        """Test handling multiple documents from loader."""
        # Mock loader that returns multiple documents
        loader = AsyncMock()
        loader.load = AsyncMock(return_value=[
            Document(page_content="Doc 1"),
            Document(page_content="Doc 2"),
            Document(page_content="Doc 3"),
        ])
        factory = Mock()
        factory.get_loader = Mock(return_value=loader)

        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "multi.pdf"
        mock_file.read = AsyncMock(return_value=b"content")

        result = await process_upload(
            file=mock_file,
            config=mock_config,
            loader_factory=factory,
            text_cleaner=mock_text_cleaner,
            text_splitter=mock_text_splitter,
            vectorstore=mock_vectorstore,
        )

        assert result.num_documents == 3


class TestTextCleaning:
    """Test text cleaning step."""

    @pytest.mark.asyncio
    async def test_cleaning_applied_when_enabled(
        self, mock_config, mock_loader_factory, mock_vectorstore, mock_text_splitter
    ):
        """Test that text cleaning is applied when enabled."""
        cleaner = Mock()
        cleaner.process = Mock(side_effect=lambda docs: docs)

        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.read = AsyncMock(return_value=b"content")

        # Enable cleaning in config
        mock_config.preprocessing.enabled = True
        mock_config.preprocessing.cleaning = True

        await process_upload(
            file=mock_file,
            config=mock_config,
            loader_factory=mock_loader_factory,
            text_cleaner=cleaner,
            text_splitter=mock_text_splitter,
            vectorstore=mock_vectorstore,
        )

        # Verify cleaner was called
        assert cleaner.process.called

    @pytest.mark.asyncio
    async def test_cleaning_skipped_when_disabled(
        self, mock_config, mock_loader_factory, mock_vectorstore, mock_text_splitter
    ):
        """Test that cleaning is skipped when disabled."""
        cleaner = Mock()
        cleaner.process = Mock(side_effect=lambda docs: docs)

        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.read = AsyncMock(return_value=b"content")

        # Disable cleaning
        mock_config.preprocessing.enabled = False

        await process_upload(
            file=mock_file,
            config=mock_config,
            loader_factory=mock_loader_factory,
            text_cleaner=cleaner,
            text_splitter=mock_text_splitter,
            vectorstore=mock_vectorstore,
        )

        # Cleaner should not be called
        assert not cleaner.process.called


class TestTextSplitting:
    """Test text splitting step."""

    @pytest.mark.asyncio
    async def test_splitter_creates_chunks(
        self, mock_config, mock_loader_factory, mock_text_cleaner, mock_vectorstore
    ):
        """Test that splitter creates multiple chunks."""
        splitter = Mock()
        splitter.split_documents = Mock(return_value=[
            Document(page_content=f"Chunk {i}") for i in range(10)
        ])

        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.read = AsyncMock(return_value=b"content")

        result = await process_upload(
            file=mock_file,
            config=mock_config,
            loader_factory=mock_loader_factory,
            text_cleaner=mock_text_cleaner,
            text_splitter=splitter,
            vectorstore=mock_vectorstore,
        )

        assert result.num_chunks == 10
        assert splitter.split_documents.called


class TestVectorStoreStorage:
    """Test vector store storage step."""

    @pytest.mark.asyncio
    async def test_chunks_added_to_vectorstore(
        self, mock_config, mock_loader_factory, mock_text_cleaner, mock_text_splitter
    ):
        """Test that chunks are added to vector store."""
        vectorstore = AsyncMock()
        vectorstore.add_documents = AsyncMock(return_value=["id1", "id2", "id3"])

        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.read = AsyncMock(return_value=b"content")

        result = await process_upload(
            file=mock_file,
            config=mock_config,
            loader_factory=mock_loader_factory,
            text_cleaner=mock_text_cleaner,
            text_splitter=mock_text_splitter,
            vectorstore=vectorstore,
        )

        # Verify vectorstore.add_documents was called
        assert vectorstore.add_documents.called
        assert len(result.document_ids) == 3


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_loader_error_propagates(
        self, mock_config, mock_text_cleaner, mock_text_splitter, mock_vectorstore
    ):
        """Test that loader errors are propagated."""
        # Mock loader that raises error
        loader = AsyncMock()
        loader.load = AsyncMock(side_effect=Exception("Loader error"))
        factory = Mock()
        factory.get_loader = Mock(return_value=loader)

        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "bad.pdf"
        mock_file.read = AsyncMock(return_value=b"content")

        with pytest.raises(Exception, match="Loader error"):
            await process_upload(
                file=mock_file,
                config=mock_config,
                loader_factory=factory,
                text_cleaner=mock_text_cleaner,
                text_splitter=mock_text_splitter,
                vectorstore=mock_vectorstore,
            )

    @pytest.mark.asyncio
    async def test_vectorstore_error_propagates(
        self, mock_config, mock_loader_factory, mock_text_cleaner, mock_text_splitter
    ):
        """Test that vectorstore errors are propagated."""
        vectorstore = AsyncMock()
        vectorstore.add_documents = AsyncMock(side_effect=Exception("DB error"))

        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.read = AsyncMock(return_value=b"content")

        with pytest.raises(Exception, match="DB error"):
            await process_upload(
                file=mock_file,
                config=mock_config,
                loader_factory=mock_loader_factory,
                text_cleaner=mock_text_cleaner,
                text_splitter=mock_text_splitter,
                vectorstore=vectorstore,
            )

    @pytest.mark.asyncio
    async def test_unicode_filename(
        self, mock_config, mock_loader_factory, mock_text_cleaner,
        mock_text_splitter, mock_vectorstore
    ):
        """Test handling Unicode characters in filename."""
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "文档.pdf"  # Chinese characters
        mock_file.read = AsyncMock(return_value=b"content")

        result = await process_upload(
            file=mock_file,
            config=mock_config,
            loader_factory=mock_loader_factory,
            text_cleaner=mock_text_cleaner,
            text_splitter=mock_text_splitter,
            vectorstore=mock_vectorstore,
        )

        assert "文档.pdf" in result.message

    @pytest.mark.asyncio
    async def test_special_characters_in_filename(
        self, mock_config, mock_loader_factory, mock_text_cleaner,
        mock_text_splitter, mock_vectorstore
    ):
        """Test handling special characters in filename."""
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "test (copy) [2024].pdf"
        mock_file.read = AsyncMock(return_value=b"content")

        result = await process_upload(
            file=mock_file,
            config=mock_config,
            loader_factory=mock_loader_factory,
            text_cleaner=mock_text_cleaner,
            text_splitter=mock_text_splitter,
            vectorstore=mock_vectorstore,
        )

        assert isinstance(result, UploadResponse)


class TestFileExtensionHandling:
    """Test handling of different file extensions."""

    @pytest.mark.asyncio
    async def test_pdf_extension_preserved(
        self, mock_config, mock_loader_factory, mock_text_cleaner,
        mock_text_splitter, mock_vectorstore
    ):
        """Test that PDF extension is preserved in temp file."""
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = "document.pdf"
        mock_file.read = AsyncMock(return_value=b"content")

        await process_upload(
            file=mock_file,
            config=mock_config,
            loader_factory=mock_loader_factory,
            text_cleaner=mock_text_cleaner,
            text_splitter=mock_text_splitter,
            vectorstore=mock_vectorstore,
        )

        # Verify get_loader was called with path ending in .pdf
        call_args = mock_loader_factory.get_loader.call_args
        temp_path = call_args[0][0]
        assert str(temp_path).endswith(".pdf")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("extension", [".txt", ".docx", ".md", ".csv"])
    async def test_various_extensions(
        self, extension, mock_config, mock_loader_factory,
        mock_text_cleaner, mock_text_splitter, mock_vectorstore
    ):
        """Test handling of various file extensions."""
        mock_file = Mock(spec=UploadFile)
        mock_file.filename = f"document{extension}"
        mock_file.read = AsyncMock(return_value=b"content")

        result = await process_upload(
            file=mock_file,
            config=mock_config,
            loader_factory=mock_loader_factory,
            text_cleaner=mock_text_cleaner,
            text_splitter=mock_text_splitter,
            vectorstore=mock_vectorstore,
        )

        assert isinstance(result, UploadResponse)
