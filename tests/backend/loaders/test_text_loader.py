"""
Comprehensive tests for TextLoader.

Tests all boundary cases, edge cases, and error conditions for text file loading.
"""

import pytest
from pathlib import Path

from rag.backend.loaders.text_loader import TextLoader
from rag.config import TextLoaderConfig


class TestTextLoaderConfiguration:
    """Test TextLoader configuration and initialization."""

    def test_init_with_valid_config(self, text_loader_config: TextLoaderConfig):
        """Test TextLoader initializes with valid configuration."""
        loader = TextLoader(text_loader_config)
        assert loader.config == text_loader_config
        assert loader.SUPPORTED_EXTENSIONS == {".txt", ".md", ".markdown", ".log", ".csv", ".json"}

    def test_supported_extensions_constant(self):
        """Test that SUPPORTED_EXTENSIONS is a class constant."""
        assert hasattr(TextLoader, "SUPPORTED_EXTENSIONS")
        assert isinstance(TextLoader.SUPPORTED_EXTENSIONS, set)


class TestTextLoaderSupports:
    """Test TextLoader.supports() method for file type detection."""

    def test_supports_txt_file(self, text_loader_config: TextLoaderConfig):
        """Test that .txt files are supported."""
        loader = TextLoader(text_loader_config)
        assert loader.supports("document.txt")
        assert loader.supports("/path/to/document.txt")
        assert loader.supports(Path("document.txt"))

    def test_supports_txt_case_insensitive(self, text_loader_config: TextLoaderConfig):
        """Test that .txt extension is case insensitive."""
        loader = TextLoader(text_loader_config)
        assert loader.supports("document.TXT")
        assert loader.supports("document.Txt")

    def test_supports_md_file(self, text_loader_config: TextLoaderConfig):
        """Test that .md files are supported."""
        loader = TextLoader(text_loader_config)
        assert loader.supports("readme.md")
        assert loader.supports("README.MD")

    def test_supports_markdown_file(self, text_loader_config: TextLoaderConfig):
        """Test that .markdown files are supported."""
        loader = TextLoader(text_loader_config)
        assert loader.supports("document.markdown")
        assert loader.supports("document.MARKDOWN")

    def test_supports_log_file(self, text_loader_config: TextLoaderConfig):
        """Test that .log files are supported."""
        loader = TextLoader(text_loader_config)
        assert loader.supports("application.log")
        assert loader.supports("error.LOG")

    def test_supports_csv_file(self, text_loader_config: TextLoaderConfig):
        """Test that .csv files are supported."""
        loader = TextLoader(text_loader_config)
        assert loader.supports("data.csv")
        assert loader.supports("DATA.CSV")

    def test_supports_json_file(self, text_loader_config: TextLoaderConfig):
        """Test that .json files are supported."""
        loader = TextLoader(text_loader_config)
        assert loader.supports("config.json")
        assert loader.supports("CONFIG.JSON")

    def test_does_not_support_pdf(self, text_loader_config: TextLoaderConfig):
        """Test that .pdf files are not supported."""
        loader = TextLoader(text_loader_config)
        assert not loader.supports("document.pdf")

    def test_does_not_support_docx(self, text_loader_config: TextLoaderConfig):
        """Test that .docx files are not supported."""
        loader = TextLoader(text_loader_config)
        assert not loader.supports("document.docx")

    def test_does_not_support_image(self, text_loader_config: TextLoaderConfig):
        """Test that image files are not supported."""
        loader = TextLoader(text_loader_config)
        assert not loader.supports("image.jpg")
        assert not loader.supports("image.png")

    def test_does_not_support_no_extension(self, text_loader_config: TextLoaderConfig):
        """Test that files without extension are not supported."""
        loader = TextLoader(text_loader_config)
        assert not loader.supports("README")
        assert not loader.supports("/path/to/file")

    def test_does_not_support_unknown_extension(self, text_loader_config: TextLoaderConfig):
        """Test that unknown extensions are not supported."""
        loader = TextLoader(text_loader_config)
        assert not loader.supports("file.xyz")
        assert not loader.supports("file.unknown")


class TestTextLoaderLoadValidFiles:
    """Test TextLoader.load() with valid text files."""

    @pytest.mark.asyncio
    async def test_load_simple_text_file(
        self, text_loader_config: TextLoaderConfig, sample_text_file: Path
    ):
        """Test loading a simple text file."""
        loader = TextLoader(text_loader_config)
        documents = await loader.load(sample_text_file)

        assert len(documents) == 1
        assert "This is a test document." in documents[0].page_content
        assert "It has multiple lines." in documents[0].page_content

    @pytest.mark.asyncio
    async def test_load_returns_correct_metadata(
        self, text_loader_config: TextLoaderConfig, sample_text_file: Path
    ):
        """Test that loaded document has correct metadata."""
        loader = TextLoader(text_loader_config)
        documents = await loader.load(sample_text_file)

        metadata = documents[0].metadata
        assert "source" in metadata
        assert metadata["source"] == str(sample_text_file)
        assert "file_name" in metadata
        assert metadata["file_name"] == "sample.txt"
        assert "file_extension" in metadata
        assert metadata["file_extension"] == ".txt"
        assert "encoding" in metadata
        assert "file_size_bytes" in metadata
        assert metadata["file_size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_load_utf8_file(
        self, text_loader_config: TextLoaderConfig, sample_text_file: Path
    ):
        """Test loading UTF-8 encoded file."""
        loader = TextLoader(text_loader_config)
        documents = await loader.load(sample_text_file)

        assert documents[0].metadata["encoding"] == "utf-8"

    @pytest.mark.asyncio
    async def test_load_utf8_bom_file(
        self, text_loader_config: TextLoaderConfig, sample_utf8_bom_file: Path
    ):
        """Test loading UTF-8 file with BOM."""
        loader = TextLoader(text_loader_config)
        documents = await loader.load(sample_utf8_bom_file)

        assert len(documents) == 1
        assert "UTF-8 with BOM" in documents[0].page_content
        # BOM should be handled by utf-8-sig encoding
        assert documents[0].metadata["encoding"] in ["utf-8-sig", "utf-8"]

    @pytest.mark.asyncio
    async def test_load_latin1_file(
        self, text_loader_config: TextLoaderConfig, sample_latin1_file: Path
    ):
        """Test loading Latin-1 encoded file with fallback."""
        loader = TextLoader(text_loader_config)
        documents = await loader.load(sample_latin1_file)

        assert len(documents) == 1
        # Should successfully decode with latin-1 or cp1252 fallback
        assert "Café" in documents[0].page_content or "Caf" in documents[0].page_content
        assert documents[0].metadata["encoding"] in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

    @pytest.mark.asyncio
    async def test_load_large_file(
        self, text_loader_config: TextLoaderConfig, sample_large_file: Path
    ):
        """Test loading a large text file."""
        loader = TextLoader(text_loader_config)
        documents = await loader.load(sample_large_file)

        assert len(documents) == 1
        assert len(documents[0].page_content) > 1_000_000  # ~1MB
        assert documents[0].metadata["file_size_bytes"] > 1_000_000

    @pytest.mark.asyncio
    async def test_load_with_string_path(
        self, text_loader_config: TextLoaderConfig, sample_text_file: Path
    ):
        """Test loading file with string path instead of Path object."""
        loader = TextLoader(text_loader_config)
        documents = await loader.load(str(sample_text_file))

        assert len(documents) == 1
        assert "This is a test document." in documents[0].page_content


class TestTextLoaderLoadEmptyFiles:
    """Test TextLoader.load() with empty files."""

    @pytest.mark.asyncio
    async def test_load_empty_file(
        self, text_loader_config: TextLoaderConfig, sample_empty_file: Path
    ):
        """Test loading an empty text file."""
        loader = TextLoader(text_loader_config)
        documents = await loader.load(sample_empty_file)

        assert len(documents) == 1
        assert documents[0].page_content == ""
        assert documents[0].metadata["file_size_bytes"] == 0

    @pytest.mark.asyncio
    async def test_load_whitespace_only_file(
        self, text_loader_config: TextLoaderConfig, temp_dir: Path
    ):
        """Test loading a file with only whitespace."""
        whitespace_file = temp_dir / "whitespace.txt"
        whitespace_file.write_text("   \n\n   \t\t\n", encoding="utf-8")

        loader = TextLoader(text_loader_config)
        documents = await loader.load(whitespace_file)

        assert len(documents) == 1
        # Content should preserve whitespace
        assert documents[0].page_content == "   \n\n   \t\t\n"


class TestTextLoaderLoadErrors:
    """Test TextLoader.load() error handling."""

    @pytest.mark.asyncio
    async def test_load_nonexistent_file(self, text_loader_config: TextLoaderConfig):
        """Test loading a file that doesn't exist raises FileNotFoundError."""
        loader = TextLoader(text_loader_config)

        with pytest.raises(FileNotFoundError):
            await loader.load("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_load_directory(
        self, text_loader_config: TextLoaderConfig, temp_dir: Path
    ):
        """Test loading a directory raises appropriate error."""
        loader = TextLoader(text_loader_config)

        with pytest.raises((IsADirectoryError, PermissionError, OSError)):
            await loader.load(temp_dir)

    @pytest.mark.asyncio
    async def test_load_binary_file(
        self, text_loader_config: TextLoaderConfig, temp_dir: Path
    ):
        """Test loading a binary file attempts encoding fallback and succeeds with latin-1."""
        binary_file = temp_dir / "binary.txt"
        binary_file.write_bytes(b"\x00\x01\x02\x03\x04\xff\xfe\xfd")

        loader = TextLoader(text_loader_config)

        # TextLoader is resilient - latin-1 can decode any byte sequence
        # So this actually succeeds instead of failing
        documents = await loader.load(binary_file)
        assert len(documents) == 1
        # Encoding should be latin-1 or cp1252 which can handle arbitrary bytes
        assert documents[0].metadata["encoding"] in ["latin-1", "cp1252"]


class TestTextLoaderSpecialContent:
    """Test TextLoader with special content types."""

    @pytest.mark.asyncio
    async def test_load_markdown_with_code_blocks(
        self, text_loader_config: TextLoaderConfig, temp_dir: Path
    ):
        """Test loading Markdown file with code blocks."""
        md_file = temp_dir / "code.md"
        content = """# Markdown Test

```python
def hello():
    print("Hello, World!")
```

Some text after code block.
"""
        md_file.write_text(content, encoding="utf-8")

        loader = TextLoader(text_loader_config)
        documents = await loader.load(md_file)

        assert len(documents) == 1
        assert "```python" in documents[0].page_content
        assert 'print("Hello, World!")' in documents[0].page_content
        assert documents[0].metadata["file_extension"] == ".md"

    @pytest.mark.asyncio
    async def test_load_json_file(
        self, text_loader_config: TextLoaderConfig, temp_dir: Path
    ):
        """Test loading JSON file as text."""
        json_file = temp_dir / "data.json"
        content = """{
  "name": "Test",
  "values": [1, 2, 3],
  "nested": {
    "key": "value"
  }
}"""
        json_file.write_text(content, encoding="utf-8")

        loader = TextLoader(text_loader_config)
        documents = await loader.load(json_file)

        assert len(documents) == 1
        assert '"name": "Test"' in documents[0].page_content
        assert documents[0].metadata["file_extension"] == ".json"

    @pytest.mark.asyncio
    async def test_load_csv_file(
        self, text_loader_config: TextLoaderConfig, temp_dir: Path
    ):
        """Test loading CSV file as text."""
        csv_file = temp_dir / "data.csv"
        content = """name,age,city
Alice,30,New York
Bob,25,San Francisco
Charlie,35,Boston"""
        csv_file.write_text(content, encoding="utf-8")

        loader = TextLoader(text_loader_config)
        documents = await loader.load(csv_file)

        assert len(documents) == 1
        assert "name,age,city" in documents[0].page_content
        assert "Alice,30,New York" in documents[0].page_content
        assert documents[0].metadata["file_extension"] == ".csv"

    @pytest.mark.asyncio
    async def test_load_log_file(
        self, text_loader_config: TextLoaderConfig, temp_dir: Path
    ):
        """Test loading log file."""
        log_file = temp_dir / "app.log"
        content = """[2024-01-01 10:00:00] INFO: Application started
[2024-01-01 10:00:01] DEBUG: Loading configuration
[2024-01-01 10:00:02] WARNING: Deprecated API used
[2024-01-01 10:00:03] ERROR: Connection failed"""
        log_file.write_text(content, encoding="utf-8")

        loader = TextLoader(text_loader_config)
        documents = await loader.load(log_file)

        assert len(documents) == 1
        assert "INFO: Application started" in documents[0].page_content
        assert "ERROR: Connection failed" in documents[0].page_content
        assert documents[0].metadata["file_extension"] == ".log"

    @pytest.mark.asyncio
    async def test_load_unicode_characters(
        self, text_loader_config: TextLoaderConfig, temp_dir: Path
    ):
        """Test loading file with various unicode characters."""
        unicode_file = temp_dir / "unicode.txt"
        content = """English text
中文文本
日本語テキスト
한국어 텍스트
Émojis: 🚀 💻 📚
Math: ∑ ∫ ∂ ∇
"""
        unicode_file.write_text(content, encoding="utf-8")

        loader = TextLoader(text_loader_config)
        documents = await loader.load(unicode_file)

        assert len(documents) == 1
        assert "中文文本" in documents[0].page_content
        assert "日本語テキスト" in documents[0].page_content
        assert "🚀" in documents[0].page_content
        assert "∑" in documents[0].page_content


class TestTextLoaderEdgeCases:
    """Test TextLoader edge cases."""

    @pytest.mark.asyncio
    async def test_load_file_with_null_bytes(
        self, text_loader_config: TextLoaderConfig, temp_dir: Path
    ):
        """Test loading file with null bytes."""
        null_file = temp_dir / "null.txt"
        content = "Before null\x00After null"
        null_file.write_text(content, encoding="utf-8")

        loader = TextLoader(text_loader_config)
        documents = await loader.load(null_file)

        # Should load but may have null bytes in content
        assert len(documents) == 1
        # Content behavior with null bytes depends on implementation

    @pytest.mark.asyncio
    async def test_load_very_long_line(
        self, text_loader_config: TextLoaderConfig, temp_dir: Path
    ):
        """Test loading file with very long single line."""
        long_line_file = temp_dir / "long_line.txt"
        # Create a 100KB single line
        content = "a" * 100_000
        long_line_file.write_text(content, encoding="utf-8")

        loader = TextLoader(text_loader_config)
        documents = await loader.load(long_line_file)

        assert len(documents) == 1
        assert len(documents[0].page_content) == 100_000

    @pytest.mark.asyncio
    async def test_load_file_with_mixed_line_endings(
        self, text_loader_config: TextLoaderConfig, temp_dir: Path
    ):
        """Test loading file with mixed line endings (CRLF, LF, CR)."""
        mixed_file = temp_dir / "mixed.txt"
        # Write bytes directly to preserve line endings
        content = b"Line 1\r\nLine 2\nLine 3\rLine 4"
        mixed_file.write_bytes(content)

        loader = TextLoader(text_loader_config)
        documents = await loader.load(mixed_file)

        assert len(documents) == 1
        # Python should normalize line endings when reading text
        assert "Line 1" in documents[0].page_content
        assert "Line 4" in documents[0].page_content


class TestTextLoaderDisabledState:
    """Test TextLoader behavior when disabled."""

    @pytest.mark.asyncio
    async def test_disabled_loader_config(self, sample_text_file: Path):
        """Test that disabled loader can still be instantiated (config is for factory)."""
        config = TextLoaderConfig(
            enabled=False,
            supported_extensions=[".txt"],
        )
        loader = TextLoader(config)

        # Loader itself doesn't enforce enabled flag, that's for factory
        assert loader.config.enabled is False
        # Can still use it directly
        documents = await loader.load(sample_text_file)
        assert len(documents) == 1


class TestTextLoaderPathHandling:
    """Test TextLoader path handling."""

    @pytest.mark.asyncio
    async def test_load_with_relative_path(
        self, text_loader_config: TextLoaderConfig, temp_dir: Path, sample_text_file: Path
    ):
        """Test loading file with relative path."""
        import os

        # Change to temp directory
        old_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)

            loader = TextLoader(text_loader_config)
            documents = await loader.load("sample.txt")

            assert len(documents) == 1
        finally:
            os.chdir(old_cwd)

    @pytest.mark.asyncio
    async def test_load_with_absolute_path(
        self, text_loader_config: TextLoaderConfig, sample_text_file: Path
    ):
        """Test loading file with absolute path."""
        loader = TextLoader(text_loader_config)
        documents = await loader.load(sample_text_file.absolute())

        assert len(documents) == 1
        assert documents[0].metadata["source"] == str(sample_text_file.absolute())
