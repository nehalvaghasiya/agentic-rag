"""
Pytest configuration and shared fixtures.

This module provides common fixtures used across all tests.
"""

import tempfile
from pathlib import Path
from typing import Generator

import pytest
from langchain_core.documents import Document

from rag.backend.embeddings.dummy_embeddings import DummyEmbeddings
from rag.config import (
    AppConfig,
    CharacterSplitterConfig,
    CleaningConfig,
    Config,
    DOCXLoaderConfig,
    ImageLoaderConfig,
    LoadersConfig,
    LoggingConfig,
    PDFLoaderConfig,
    PreprocessingConfig,
    RecursiveSplitterConfig,
    SemanticSplitterConfig,
    SplittingConfig,
    SummarizationConfig,
    TextLoaderConfig,
    TokenSplitterConfig,
    WebsiteLoaderConfig,
)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Create a temporary directory for test files.

    Yields:
        Path to temporary directory that is cleaned up after test.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_text_file(temp_dir: Path) -> Path:
    """
    Create a sample text file for testing.

    Args:
        temp_dir: Temporary directory fixture.

    Returns:
        Path to created text file.
    """
    file_path = temp_dir / "sample.txt"
    file_path.write_text("This is a test document.\nIt has multiple lines.\n", encoding="utf-8")
    return file_path


@pytest.fixture
def sample_empty_file(temp_dir: Path) -> Path:
    """
    Create an empty file for testing.

    Args:
        temp_dir: Temporary directory fixture.

    Returns:
        Path to created empty file.
    """
    file_path = temp_dir / "empty.txt"
    file_path.write_text("", encoding="utf-8")
    return file_path


@pytest.fixture
def sample_utf8_bom_file(temp_dir: Path) -> Path:
    """
    Create a UTF-8 BOM file for testing encoding detection.

    Args:
        temp_dir: Temporary directory fixture.

    Returns:
        Path to created file with BOM.
    """
    file_path = temp_dir / "utf8_bom.txt"
    file_path.write_bytes(b"\xef\xbb\xbfUTF-8 with BOM")
    return file_path


@pytest.fixture
def sample_latin1_file(temp_dir: Path) -> Path:
    """
    Create a Latin-1 encoded file.

    Args:
        temp_dir: Temporary directory fixture.

    Returns:
        Path to created Latin-1 file.
    """
    file_path = temp_dir / "latin1.txt"
    file_path.write_bytes("Café résumé naïve".encode("latin-1"))
    return file_path


@pytest.fixture
def sample_large_file(temp_dir: Path) -> Path:
    """
    Create a large text file for performance testing.

    Args:
        temp_dir: Temporary directory fixture.

    Returns:
        Path to created large file.
    """
    file_path = temp_dir / "large.txt"
    # Create a ~1MB file
    content = "This is a test line.\n" * 50000
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def sample_documents() -> list[Document]:
    """
    Create sample LangChain documents for testing.

    Returns:
        List of sample documents.
    """
    return [
        Document(
            page_content="This is the first document.",
            metadata={"source": "doc1.txt", "page": 1},
        ),
        Document(
            page_content="This is the second document.",
            metadata={"source": "doc2.txt", "page": 1},
        ),
        Document(
            page_content="This is a longer third document with more content to test splitting.",
            metadata={"source": "doc3.txt", "page": 1},
        ),
    ]


@pytest.fixture
def sample_long_document() -> Document:
    """
    Create a long document for splitting tests.

    Returns:
        Long document.
    """
    content = " ".join([f"Sentence {i}." for i in range(100)])
    return Document(page_content=content, metadata={"source": "long.txt"})


@pytest.fixture
def app_config() -> AppConfig:
    """
    Create a test app configuration.

    Returns:
        AppConfig instance.
    """
    return AppConfig(
        name="Test RAG",
        version="1.0.0",
        debug=True,
        max_upload_size_mb=10,
    )


@pytest.fixture
def logging_config() -> LoggingConfig:
    """
    Create a test logging configuration.

    Returns:
        LoggingConfig instance.
    """
    return LoggingConfig(
        level="DEBUG",
        log_file="logs/test.log",
        rotation="10 MB",
        retention="7 days",
        format="{message}",
    )


@pytest.fixture
def pdf_loader_config() -> PDFLoaderConfig:
    """
    Create a test PDF loader configuration.

    Returns:
        PDFLoaderConfig instance.
    """
    return PDFLoaderConfig(enabled=True, extract_images=True)


@pytest.fixture
def docx_loader_config() -> DOCXLoaderConfig:
    """
    Create a test DOCX loader configuration.

    Returns:
        DOCXLoaderConfig instance.
    """
    return DOCXLoaderConfig(enabled=True)


@pytest.fixture
def text_loader_config() -> TextLoaderConfig:
    """
    Create a test text loader configuration.

    Returns:
        TextLoaderConfig instance.
    """
    return TextLoaderConfig(
        enabled=True,
        supported_extensions=[".txt", ".md", ".markdown", ".log", ".csv", ".json"],
    )


@pytest.fixture
def website_loader_config() -> WebsiteLoaderConfig:
    """
    Create a test website loader configuration.

    Returns:
        WebsiteLoaderConfig instance.
    """
    return WebsiteLoaderConfig(
        enabled=True,
        timeout_seconds=30,
        user_agent="Test User Agent",
        max_pages=10,
    )


@pytest.fixture
def image_loader_config() -> ImageLoaderConfig:
    """
    Create a test image loader configuration.

    Returns:
        ImageLoaderConfig instance.
    """
    return ImageLoaderConfig(
        enabled=True,
        ocr_enabled=True,
        supported_formats=[".jpg", ".jpeg", ".png", ".gif"],
    )


@pytest.fixture
def cleaning_config() -> CleaningConfig:
    """
    Create a test cleaning configuration.

    Returns:
        CleaningConfig instance.
    """
    return CleaningConfig(
        remove_extra_whitespace=True,
        remove_special_chars=False,
        lowercase=False,
    )


@pytest.fixture
def summarization_config() -> SummarizationConfig:
    """
    Create a test summarization configuration.

    Returns:
        SummarizationConfig instance.
    """
    return SummarizationConfig(
        enabled=False,
        model_provider="openai",
        max_chunk_length=2000,
    )


@pytest.fixture
def preprocessing_config(
    cleaning_config: CleaningConfig, summarization_config: SummarizationConfig
) -> PreprocessingConfig:
    """
    Create a test preprocessing configuration.

    Args:
        cleaning_config: CleaningConfig fixture.
        summarization_config: SummarizationConfig fixture.

    Returns:
        PreprocessingConfig instance.
    """
    return PreprocessingConfig(
        enabled=True,
        cleaning=cleaning_config,
        summarization=summarization_config,
    )


@pytest.fixture
def recursive_splitter_config() -> RecursiveSplitterConfig:
    """
    Create a test recursive splitter configuration.

    Returns:
        RecursiveSplitterConfig instance.
    """
    return RecursiveSplitterConfig(
        chunk_size=100,
        chunk_overlap=20,
        separators=["\n\n", "\n", " ", ""],
    )


@pytest.fixture
def character_splitter_config() -> CharacterSplitterConfig:
    """
    Create a test character splitter configuration.

    Returns:
        CharacterSplitterConfig instance.
    """
    return CharacterSplitterConfig(
        chunk_size=100,
        chunk_overlap=20,
        separator="\n",
    )


@pytest.fixture
def token_splitter_config() -> TokenSplitterConfig:
    """
    Create a test token splitter configuration.

    Returns:
        TokenSplitterConfig instance.
    """
    return TokenSplitterConfig(
        chunk_size=50,
        chunk_overlap=10,
        encoding_name="cl100k_base",
    )


@pytest.fixture
def semantic_splitter_config() -> SemanticSplitterConfig:
    """
    Create a test semantic splitter configuration.

    Returns:
        SemanticSplitterConfig instance.
    """
    return SemanticSplitterConfig(
        buffer_size=1,
        breakpoint_threshold_type="percentile",
    )


@pytest.fixture
def splitting_config(
    recursive_splitter_config: RecursiveSplitterConfig,
    character_splitter_config: CharacterSplitterConfig,
    token_splitter_config: TokenSplitterConfig,
    semantic_splitter_config: SemanticSplitterConfig,
) -> SplittingConfig:
    """
    Create a test splitting configuration.

    Args:
        recursive_splitter_config: RecursiveSplitterConfig fixture.
        character_splitter_config: CharacterSplitterConfig fixture.
        token_splitter_config: TokenSplitterConfig fixture.
        semantic_splitter_config: SemanticSplitterConfig fixture.

    Returns:
        SplittingConfig instance.
    """
    return SplittingConfig(
        strategy="recursive",
        recursive=recursive_splitter_config,
        character=character_splitter_config,
        token=token_splitter_config,
        semantic=semantic_splitter_config,
    )


@pytest.fixture
def dummy_embeddings() -> DummyEmbeddings:
    """
    Create dummy embeddings for testing.

    Returns:
        DummyEmbeddings instance.
    """
    return DummyEmbeddings(dimensions=384)


# ==================== Loader Factory Fixtures ====================


@pytest.fixture
def app_config() -> Config:
    """
    Create application config with default settings.

    Returns:
        Config instance loaded from config.yaml.
    """
    from rag.config import load_config
    return load_config()


@pytest.fixture
def config_all_loaders(app_config) -> Config:
    """
    Create config with all loaders enabled.

    Returns:
        Config with all loaders enabled.
    """
    app_config.loaders.pdf.enabled = True
    app_config.loaders.docx.enabled = True
    app_config.loaders.text.enabled = True
    app_config.loaders.website.enabled = True
    app_config.loaders.image.enabled = True
    return app_config


@pytest.fixture
def config_pdf_only(app_config) -> Config:
    """
    Create config with only PDF loader enabled.

    Returns:
        Config with only PDF loader enabled.
    """
    app_config.loaders.pdf.enabled = True
    app_config.loaders.docx.enabled = False
    app_config.loaders.text.enabled = False
    app_config.loaders.website.enabled = False
    app_config.loaders.image.enabled = False
    return app_config


@pytest.fixture
def config_no_loaders(app_config) -> Config:
    """
    Create config with all loaders disabled.

    Returns:
        Config with no loaders enabled.
    """
    app_config.loaders.pdf.enabled = False
    app_config.loaders.docx.enabled = False
    app_config.loaders.text.enabled = False
    app_config.loaders.website.enabled = False
    app_config.loaders.image.enabled = False
    return app_config
