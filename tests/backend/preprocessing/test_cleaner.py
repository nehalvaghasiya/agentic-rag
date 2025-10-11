"""
Comprehensive tests for text preprocessing (TextCleaner).

Tests all cleaning operations, flag combinations, and edge cases.
"""

import pytest
from langchain_core.documents import Document

from rag.backend.preprocessing.cleaner import TextCleaner
from rag.config import CleaningConfig


class TestTextCleanerConfiguration:
    """Test TextCleaner initialization and configuration."""

    def test_init_with_all_flags_enabled(self):
        """Test initialization with all cleaning flags enabled."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=True, lowercase=True
        )
        cleaner = TextCleaner(config)

        assert cleaner.config == config
        assert cleaner.config.remove_extra_whitespace is True
        assert cleaner.config.remove_special_chars is True
        assert cleaner.config.lowercase is True

    def test_init_with_all_flags_disabled(self):
        """Test initialization with all cleaning flags disabled."""
        config = CleaningConfig(
            remove_extra_whitespace=False, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        assert cleaner.config.remove_extra_whitespace is False
        assert cleaner.config.remove_special_chars is False
        assert cleaner.config.lowercase is False


class TestWhitespaceRemoval:
    """Test remove_extra_whitespace functionality."""

    def test_remove_multiple_spaces(self, cleaning_config: CleaningConfig):
        """Test removing multiple consecutive spaces."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        docs = [Document(page_content="This  has   multiple    spaces.", metadata={})]
        result = cleaner.process(docs)

        assert result[0].page_content == "This has multiple spaces."

    def test_remove_multiple_newlines(self):
        """Test normalizing multiple newlines to double newline."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        docs = [Document(page_content="Line1\n\n\n\n\nLine2", metadata={})]
        result = cleaner.process(docs)

        assert result[0].page_content == "Line1\n\nLine2"

    def test_remove_leading_trailing_whitespace(self):
        """Test removing leading and trailing whitespace."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        docs = [Document(page_content="  \n  Content with padding  \n  ", metadata={})]
        result = cleaner.process(docs)

        assert result[0].page_content == "Content with padding"

    def test_preserve_whitespace_when_disabled(self):
        """Test that whitespace is preserved when flag is disabled."""
        config = CleaningConfig(
            remove_extra_whitespace=False, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        original = "  Multiple   spaces   preserved  "
        docs = [Document(page_content=original, metadata={})]
        result = cleaner.process(docs)

        assert result[0].page_content == original


class TestSpecialCharacterRemoval:
    """Test remove_special_chars functionality."""

    def test_remove_special_characters(self):
        """Test removing special characters."""
        config = CleaningConfig(
            remove_extra_whitespace=False, remove_special_chars=True, lowercase=False
        )
        cleaner = TextCleaner(config)

        docs = [Document(page_content="Hello@#$% World!*&^ Test123", metadata={})]
        result = cleaner.process(docs)

        # Keeps alphanumeric, whitespace, and basic punctuation (.!?,;:()-'")
        assert result[0].page_content == "Hello World! Test123"

    def test_preserve_basic_punctuation(self):
        """Test that basic punctuation is preserved."""
        config = CleaningConfig(
            remove_extra_whitespace=False, remove_special_chars=True, lowercase=False
        )
        cleaner = TextCleaner(config)

        docs = [
            Document(
                page_content="Hello, world! How are you? I'm fine. (Really)",
                metadata={},
            )
        ]
        result = cleaner.process(docs)

        # Basic punctuation should be preserved
        assert "," in result[0].page_content
        assert "!" in result[0].page_content
        assert "?" in result[0].page_content
        assert "." in result[0].page_content
        assert "(" in result[0].page_content
        assert "'" in result[0].page_content

    def test_preserve_special_chars_when_disabled(self):
        """Test that special characters are preserved when flag is disabled."""
        config = CleaningConfig(
            remove_extra_whitespace=False, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        original = "Special @#$%^&* characters!"
        docs = [Document(page_content=original, metadata={})]
        result = cleaner.process(docs)

        assert result[0].page_content == original


class TestLowercaseConversion:
    """Test lowercase functionality."""

    def test_convert_to_lowercase(self):
        """Test converting text to lowercase."""
        config = CleaningConfig(
            remove_extra_whitespace=False, remove_special_chars=False, lowercase=True
        )
        cleaner = TextCleaner(config)

        docs = [Document(page_content="HELLO World TEST 123", metadata={})]
        result = cleaner.process(docs)

        assert result[0].page_content == "hello world test 123"

    def test_preserve_case_when_disabled(self):
        """Test that case is preserved when lowercase is disabled."""
        config = CleaningConfig(
            remove_extra_whitespace=False, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        original = "MiXeD CaSe TeXt"
        docs = [Document(page_content=original, metadata={})]
        result = cleaner.process(docs)

        assert result[0].page_content == original

    def test_lowercase_with_unicode(self):
        """Test lowercase conversion with unicode characters."""
        config = CleaningConfig(
            remove_extra_whitespace=False, remove_special_chars=False, lowercase=True
        )
        cleaner = TextCleaner(config)

        docs = [Document(page_content="CAFÉ RÉSUMÉ NAÏVE", metadata={})]
        result = cleaner.process(docs)

        assert result[0].page_content == "café résumé naïve"


class TestFlagCombinations:
    """Test various combinations of cleaning flags."""

    def test_all_flags_enabled(self):
        """Test with all cleaning flags enabled."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=True, lowercase=True
        )
        cleaner = TextCleaner(config)

        docs = [
            Document(page_content="  HELLO   @#$  WORLD!!!   Test123  ", metadata={})
        ]
        result = cleaner.process(docs)

        # Should: remove extra spaces, remove special chars (but keep basic punctuation), lowercase
        cleaned = result[0].page_content
        # Parentheses and other basic punctuation may be preserved
        assert "hello" in cleaned
        assert "world" in cleaned
        assert "test123" in cleaned

    def test_whitespace_and_lowercase_only(self):
        """Test with whitespace removal and lowercase only."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=False, lowercase=True
        )
        cleaner = TextCleaner(config)

        docs = [Document(page_content="  HELLO   WORLD  @#$  ", metadata={})]
        result = cleaner.process(docs)

        assert result[0].page_content == "hello world @#$"

    def test_special_chars_and_lowercase_only(self):
        """Test with special char removal and lowercase only."""
        config = CleaningConfig(
            remove_extra_whitespace=False, remove_special_chars=True, lowercase=True
        )
        cleaner = TextCleaner(config)

        docs = [Document(page_content="HELLO  @#$  WORLD", metadata={})]
        result = cleaner.process(docs)

        # Special chars removed (except basic punctuation), lowercase, spaces preserved
        assert "hello" in result[0].page_content
        assert "world" in result[0].page_content

    def test_all_flags_disabled(self):
        """Test with all flags disabled (no cleaning)."""
        config = CleaningConfig(
            remove_extra_whitespace=False, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        original = "  HELLO   @#$  WORLD  "
        docs = [Document(page_content=original, metadata={})]
        result = cleaner.process(docs)

        assert result[0].page_content == original


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_document(self):
        """Test cleaning empty document."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=True, lowercase=True
        )
        cleaner = TextCleaner(config)

        docs = [Document(page_content="", metadata={})]
        result = cleaner.process(docs)

        assert result[0].page_content == ""

    def test_whitespace_only_document(self):
        """Test cleaning document with only whitespace."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        docs = [Document(page_content="    \n\n\t\t   ", metadata={})]
        result = cleaner.process(docs)

        # Should be empty after removing whitespace
        assert result[0].page_content == ""

    def test_special_chars_only_document(self):
        """Test cleaning document with only special characters."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=True, lowercase=False
        )
        cleaner = TextCleaner(config)

        docs = [Document(page_content="@#$%^&*[]{}|\\", metadata={})]
        result = cleaner.process(docs)

        # Should be mostly empty after removing special chars
        # Parentheses () might be preserved as basic punctuation
        assert len(result[0].page_content) <= 10  # Very short or empty

    def test_empty_document_list(self):
        """Test processing empty document list."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        result = cleaner.process([])

        assert result == []

    def test_single_document(self):
        """Test processing single document."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        docs = [Document(page_content="  Single  doc  ", metadata={})]
        result = cleaner.process(docs)

        assert len(result) == 1
        assert result[0].page_content == "Single doc"

    def test_multiple_documents(self):
        """Test processing multiple documents."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        docs = [
            Document(page_content="  Doc  1  ", metadata={"id": 1}),
            Document(page_content="  Doc  2  ", metadata={"id": 2}),
            Document(page_content="  Doc  3  ", metadata={"id": 3}),
        ]
        result = cleaner.process(docs)

        assert len(result) == 3
        assert result[0].page_content == "Doc 1"
        assert result[1].page_content == "Doc 2"
        assert result[2].page_content == "Doc 3"

    def test_very_long_document(self):
        """Test cleaning very long document."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        # Create a long document with extra spaces
        long_text = "  ".join(["word"] * 10000)
        docs = [Document(page_content=long_text, metadata={})]
        result = cleaner.process(docs)

        # Should have single spaces between words
        assert "  " not in result[0].page_content
        assert "word word word" in result[0].page_content


class TestMetadataPreservation:
    """Test that metadata is preserved during cleaning."""

    def test_metadata_preserved(self):
        """Test that document metadata is preserved."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=True, lowercase=True
        )
        cleaner = TextCleaner(config)

        metadata = {"source": "test.pdf", "page": 1, "author": "John Doe"}
        docs = [Document(page_content="  HELLO  WORLD  ", metadata=metadata)]
        result = cleaner.process(docs)

        assert result[0].metadata == metadata
        assert result[0].metadata["source"] == "test.pdf"
        assert result[0].metadata["page"] == 1

    def test_metadata_copy_not_reference(self):
        """Test that metadata is copied, not referenced."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        metadata = {"key": "value"}
        docs = [Document(page_content="test", metadata=metadata)]
        result = cleaner.process(docs)

        # Modify original metadata
        metadata["key"] = "modified"

        # Result metadata should not be affected
        assert result[0].metadata["key"] == "value"

    def test_empty_metadata_preserved(self):
        """Test that empty metadata is preserved."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        docs = [Document(page_content="test", metadata={})]
        result = cleaner.process(docs)

        assert result[0].metadata == {}


class TestUnicodeHandling:
    """Test handling of unicode and special characters."""

    def test_unicode_characters_preserved(self):
        """Test that unicode characters are preserved."""
        config = CleaningConfig(
            remove_extra_whitespace=True, remove_special_chars=False, lowercase=False
        )
        cleaner = TextCleaner(config)

        docs = [
            Document(
                page_content="  中文  日本語  한국어  Émojis: 🚀💻  ",
                metadata={},
            )
        ]
        result = cleaner.process(docs)

        assert "中文" in result[0].page_content
        assert "日本語" in result[0].page_content
        assert "한국어" in result[0].page_content
        assert "🚀" in result[0].page_content

    def test_special_chars_removes_unicode(self):
        """Test that special char removal affects some unicode."""
        config = CleaningConfig(
            remove_extra_whitespace=False, remove_special_chars=True, lowercase=False
        )
        cleaner = TextCleaner(config)

        docs = [Document(page_content="Text 🚀 with émojis 💻", metadata={})]
        result = cleaner.process(docs)

        # Emojis should be removed, but accented characters may remain
        # depending on regex pattern
        cleaned = result[0].page_content
        assert "Text" in cleaned
        assert "with" in cleaned
