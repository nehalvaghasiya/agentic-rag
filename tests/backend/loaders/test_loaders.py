"""
Tests for document loaders.

These tests verify that document loaders work correctly with different file types.
"""

import pytest
from pathlib import Path

from rag.backend.loaders.pdf_loader import PDFLoader
from rag.backend.loaders.docx_loader import DOCXLoader
from rag.backend.loaders.factory import LoaderFactory
from rag.config import load_config


@pytest.fixture
def config():
    """Load test configuration."""
    return load_config("config.yaml")


@pytest.fixture
def loader_factory(config):
    """Create loader factory."""
    return LoaderFactory(config)


def test_pdf_loader_supports():
    """Test PDF loader file detection."""
    from rag.config import PDFLoaderConfig

    config = PDFLoaderConfig(enabled=True, extract_images=True)
    loader = PDFLoader(config)

    assert loader.supports("document.pdf")
    assert loader.supports("file.PDF")
    assert not loader.supports("document.docx")
    assert not loader.supports("image.jpg")


def test_docx_loader_supports():
    """Test DOCX loader file detection."""
    from rag.config import DOCXLoaderConfig

    config = DOCXLoaderConfig(enabled=True)
    loader = DOCXLoader(config)

    assert loader.supports("document.docx")
    assert loader.supports("file.DOCX")
    assert not loader.supports("document.pdf")
    assert not loader.supports("image.jpg")


def test_loader_factory_get_loader(loader_factory):
    """Test that factory returns correct loader for file type."""
    pdf_loader = loader_factory.get_loader("test.pdf")
    assert isinstance(pdf_loader, PDFLoader)

    docx_loader = loader_factory.get_loader("test.docx")
    assert isinstance(docx_loader, DOCXLoader)


def test_loader_factory_unsupported_file(loader_factory):
    """Test that factory raises error for unsupported file."""
    with pytest.raises(ValueError, match="No loader available"):
        loader_factory.get_loader("test.xyz")


@pytest.mark.asyncio
async def test_pdf_loader_file_not_found():
    """Test PDF loader with non-existent file."""
    from rag.config import PDFLoaderConfig

    config = PDFLoaderConfig(enabled=True, extract_images=True)
    loader = PDFLoader(config)

    with pytest.raises(FileNotFoundError):
        await loader.load("nonexistent.pdf")
