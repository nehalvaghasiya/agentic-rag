"""
Comprehensive tests for LoaderFactory.

Tests factory pattern for document loader selection and registration.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock

from rag.backend.loaders.factory import LoaderFactory
from rag.backend.loaders.base import DocumentLoader
from rag.backend.loaders.pdf_loader import PDFLoader
from rag.backend.loaders.docx_loader import DOCXLoader
from rag.backend.loaders.text_loader import TextLoader
from rag.backend.loaders.website_loader import WebsiteLoader
from rag.backend.loaders.image_loader import ImageLoader


class TestLoaderFactoryInitialization:
    """Test LoaderFactory initialization."""

    def test_init_with_all_loaders_enabled(self, config_all_loaders):
        """Test initialization with all loaders enabled."""
        factory = LoaderFactory(config_all_loaders)

        assert factory is not None
        assert len(factory._loaders) == 5  # PDF, DOCX, Text, Website, Image

    def test_init_with_pdf_only(self, config_pdf_only):
        """Test initialization with only PDF loader enabled."""
        factory = LoaderFactory(config_pdf_only)

        assert len(factory._loaders) == 1
        assert isinstance(factory._loaders[0], PDFLoader)

    def test_init_with_no_loaders(self, config_no_loaders):
        """Test initialization with all loaders disabled."""
        factory = LoaderFactory(config_no_loaders)

        assert len(factory._loaders) == 0

    def test_init_stores_config(self, config_all_loaders):
        """Test that factory stores configuration."""
        factory = LoaderFactory(config_all_loaders)

        assert factory.config == config_all_loaders


class TestGetLoaderForPDF:
    """Test loader selection for PDF files."""

    def test_get_loader_for_pdf_string(self, config_all_loaders):
        """Test selecting loader for PDF file path string."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader("document.pdf")

        assert isinstance(loader, PDFLoader)

    def test_get_loader_for_pdf_path(self, config_all_loaders):
        """Test selecting loader for PDF file Path object."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader(Path("document.pdf"))

        assert isinstance(loader, PDFLoader)

    def test_get_loader_for_pdf_uppercase(self, config_all_loaders):
        """Test selecting loader for .PDF (uppercase) extension."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader("document.PDF")

        assert isinstance(loader, PDFLoader)

    def test_get_loader_for_pdf_with_path(self, config_all_loaders):
        """Test selecting loader for PDF with full path."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader("/path/to/document.pdf")

        assert isinstance(loader, PDFLoader)


class TestGetLoaderForDOCX:
    """Test loader selection for DOCX files."""

    def test_get_loader_for_docx(self, config_all_loaders):
        """Test selecting loader for DOCX file."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader("document.docx")

        assert isinstance(loader, DOCXLoader)

    def test_get_loader_for_docx_uppercase(self, config_all_loaders):
        """Test selecting loader for .DOCX (uppercase)."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader("document.DOCX")

        assert isinstance(loader, DOCXLoader)


class TestGetLoaderForText:
    """Test loader selection for text files."""

    def test_get_loader_for_txt(self, config_all_loaders):
        """Test selecting loader for TXT file."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader("document.txt")

        assert isinstance(loader, TextLoader)

    def test_get_loader_for_md(self, config_all_loaders):
        """Test selecting loader for Markdown file."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader("document.md")

        assert isinstance(loader, TextLoader)

    def test_get_loader_for_csv(self, config_all_loaders):
        """Test selecting loader for CSV file."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader("data.csv")

        assert isinstance(loader, TextLoader)

    def test_get_loader_for_json(self, config_all_loaders):
        """Test selecting loader for JSON file."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader("data.json")

        assert isinstance(loader, TextLoader)


class TestGetLoaderForWebsite:
    """Test loader selection for websites."""

    def test_get_loader_for_http_url(self, config_all_loaders):
        """Test selecting loader for HTTP URL."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader("http://example.com")

        assert isinstance(loader, WebsiteLoader)

    def test_get_loader_for_https_url(self, config_all_loaders):
        """Test selecting loader for HTTPS URL."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader("https://example.com/page")

        assert isinstance(loader, WebsiteLoader)

    def test_get_loader_for_url_with_params(self, config_all_loaders):
        """Test selecting loader for URL with query parameters."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader("https://example.com/page?id=123&foo=bar")

        assert isinstance(loader, WebsiteLoader)


class TestGetLoaderForImage:
    """Test loader selection for images."""

    def test_get_loader_for_png(self, config_all_loaders):
        """Test selecting loader for PNG image."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader("image.png")

        assert isinstance(loader, ImageLoader)

    def test_get_loader_for_jpg(self, config_all_loaders):
        """Test selecting loader for JPG image."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader("image.jpg")

        assert isinstance(loader, ImageLoader)

    def test_get_loader_for_jpeg(self, config_all_loaders):
        """Test selecting loader for JPEG image."""
        factory = LoaderFactory(config_all_loaders)
        loader = factory.get_loader("photo.jpeg")

        assert isinstance(loader, ImageLoader)


class TestGetLoaderErrors:
    """Test error handling in get_loader."""

    def test_get_loader_unsupported_extension_raises_error(self, config_all_loaders):
        """Test that unsupported file type raises ValueError."""
        factory = LoaderFactory(config_all_loaders)

        with pytest.raises(ValueError, match="No loader available"):
            factory.get_loader("document.xyz")

    def test_get_loader_no_extension_raises_error(self, config_all_loaders):
        """Test that file without extension raises error."""
        factory = LoaderFactory(config_all_loaders)

        with pytest.raises(ValueError, match="No loader available"):
            factory.get_loader("document_no_extension")

    def test_get_loader_when_no_loaders_enabled(self, config_no_loaders):
        """Test error when trying to get loader with none enabled."""
        factory = LoaderFactory(config_no_loaders)

        with pytest.raises(ValueError, match="No loader available"):
            factory.get_loader("document.pdf")

    def test_get_loader_when_specific_loader_disabled(self, config_pdf_only):
        """Test error when requested loader is disabled."""
        factory = LoaderFactory(config_pdf_only)

        # PDF is enabled, DOCX is not
        loader = factory.get_loader("doc.pdf")  # Should work
        assert isinstance(loader, PDFLoader)

        # DOCX should fail
        with pytest.raises(ValueError, match="No loader available"):
            factory.get_loader("doc.docx")


class TestRegisterLoader:
    """Test custom loader registration."""

    def test_register_custom_loader(self, config_no_loaders):
        """Test registering a custom loader."""
        factory = LoaderFactory(config_no_loaders)

        # Create mock custom loader
        custom_loader = Mock(spec=DocumentLoader)
        custom_loader.supports.return_value = True

        factory.register_loader(custom_loader)

        assert custom_loader in factory._loaders
        assert len(factory._loaders) == 1

    def test_custom_loader_used_for_matching_source(self, config_no_loaders):
        """Test that registered custom loader is used."""
        factory = LoaderFactory(config_no_loaders)

        # Create custom loader that supports .custom extension
        custom_loader = Mock(spec=DocumentLoader)
        custom_loader.supports = lambda s: str(s).endswith(".custom")

        factory.register_loader(custom_loader)

        # Should return our custom loader
        loader = factory.get_loader("file.custom")
        assert loader == custom_loader

    def test_register_multiple_custom_loaders(self, config_no_loaders):
        """Test registering multiple custom loaders."""
        factory = LoaderFactory(config_no_loaders)

        loader1 = Mock(spec=DocumentLoader)
        loader2 = Mock(spec=DocumentLoader)

        factory.register_loader(loader1)
        factory.register_loader(loader2)

        assert len(factory._loaders) == 2
        assert loader1 in factory._loaders
        assert loader2 in factory._loaders

    def test_custom_loader_priority(self, config_all_loaders):
        """Test that custom loaders are checked in order."""
        factory = LoaderFactory(config_all_loaders)
        initial_count = len(factory._loaders)

        # Register custom loader that supports PDFs
        custom_loader = Mock(spec=DocumentLoader)
        custom_loader.supports = lambda s: str(s).endswith(".pdf")

        factory.register_loader(custom_loader)

        # Should check loaders in order - built-in PDF loader comes first
        loader = factory.get_loader("test.pdf")
        assert isinstance(loader, PDFLoader)  # Built-in loader has priority


class TestLoaderSelection:
    """Test loader selection logic."""

    def test_first_matching_loader_selected(self, config_all_loaders):
        """Test that first matching loader is selected."""
        factory = LoaderFactory(config_all_loaders)

        # Text files could theoretically match multiple loaders,
        # but first one wins
        loader = factory.get_loader("test.txt")
        assert isinstance(loader, TextLoader)

    def test_path_object_handled_correctly(self, config_all_loaders):
        """Test that Path objects are handled correctly."""
        factory = LoaderFactory(config_all_loaders)

        path = Path("/home/user/documents/report.pdf")
        loader = factory.get_loader(path)

        assert isinstance(loader, PDFLoader)

    def test_complex_path_with_dots(self, config_all_loaders):
        """Test handling path with multiple dots."""
        factory = LoaderFactory(config_all_loaders)

        loader = factory.get_loader("my.document.v2.pdf")
        assert isinstance(loader, PDFLoader)


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_string_source(self, config_all_loaders):
        """Test handling empty string source."""
        factory = LoaderFactory(config_all_loaders)

        with pytest.raises(ValueError, match="No loader available"):
            factory.get_loader("")

    def test_whitespace_only_source(self, config_all_loaders):
        """Test handling whitespace-only source."""
        factory = LoaderFactory(config_all_loaders)

        with pytest.raises(ValueError, match="No loader available"):
            factory.get_loader("   ")

    def test_special_characters_in_filename(self, config_all_loaders):
        """Test handling special characters in filename."""
        factory = LoaderFactory(config_all_loaders)

        loader = factory.get_loader("my-file_v2 (final).pdf")
        assert isinstance(loader, PDFLoader)

    def test_unicode_filename(self, config_all_loaders):
        """Test handling Unicode in filename."""
        factory = LoaderFactory(config_all_loaders)

        loader = factory.get_loader("документ.pdf")
        assert isinstance(loader, PDFLoader)

    def test_url_encoded_filename(self, config_all_loaders):
        """Test handling URL-encoded filename."""
        factory = LoaderFactory(config_all_loaders)

        loader = factory.get_loader("my%20document.pdf")
        assert isinstance(loader, PDFLoader)


class TestLoaderFactoryConfiguration:
    """Test factory configuration."""

    def test_selective_loader_enabling(self, app_config):
        """Test enabling only specific loaders."""
        # Enable only PDF and Text
        app_config.loaders.pdf.enabled = True
        app_config.loaders.docx.enabled = False
        app_config.loaders.text.enabled = True
        app_config.loaders.website.enabled = False
        app_config.loaders.image.enabled = False

        factory = LoaderFactory(app_config)

        assert len(factory._loaders) == 2
        # Should have PDF and Text loaders
        loader_types = {type(loader) for loader in factory._loaders}
        assert PDFLoader in loader_types
        assert TextLoader in loader_types
        assert DOCXLoader not in loader_types

    def test_factory_respects_disabled_loaders(self, app_config):
        """Test that disabled loaders are not available."""
        # Disable all except PDF
        app_config.loaders.pdf.enabled = True
        app_config.loaders.docx.enabled = False
        app_config.loaders.text.enabled = False
        app_config.loaders.website.enabled = False
        app_config.loaders.image.enabled = False

        factory = LoaderFactory(app_config)

        # PDF should work
        loader = factory.get_loader("doc.pdf")
        assert isinstance(loader, PDFLoader)

        # Others should fail
        with pytest.raises(ValueError):
            factory.get_loader("doc.txt")

        with pytest.raises(ValueError):
            factory.get_loader("doc.docx")


class TestLoaderFactoryStatePersistence:
    """Test factory state management."""

    def test_loader_instances_reused(self, config_all_loaders):
        """Test that same loader instances are reused."""
        factory = LoaderFactory(config_all_loaders)

        loader1 = factory.get_loader("file1.pdf")
        loader2 = factory.get_loader("file2.pdf")

        # Should be the same loader instance
        assert loader1 is loader2

    def test_factory_instances_independent(self, config_all_loaders):
        """Test that different factory instances are independent."""
        factory1 = LoaderFactory(config_all_loaders)
        factory2 = LoaderFactory(config_all_loaders)

        # Should have different loader instances
        assert factory1._loaders[0] is not factory2._loaders[0]

    def test_registered_loaders_persist(self, config_all_loaders):
        """Test that registered loaders persist in factory."""
        factory = LoaderFactory(config_all_loaders)
        initial_count = len(factory._loaders)

        custom_loader = Mock(spec=DocumentLoader)
        factory.register_loader(custom_loader)

        # Should still have the custom loader
        assert len(factory._loaders) == initial_count + 1
        assert custom_loader in factory._loaders

        # Register another
        custom_loader2 = Mock(spec=DocumentLoader)
        factory.register_loader(custom_loader2)

        assert len(factory._loaders) == initial_count + 2
