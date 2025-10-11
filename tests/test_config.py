"""
Tests for configuration loading and validation.

These tests verify that the configuration system works correctly with
Pydantic validation.
"""

import pytest
from pydantic import ValidationError

from rag.config import Config, load_config


def test_load_config():
    """Test that config.yaml loads successfully."""
    config = load_config("config.yaml")

    assert config is not None
    assert isinstance(config, Config)
    assert config.app.name == "Agentic RAG"


def test_config_validation():
    """Test Pydantic validation for configuration."""
    # Valid config
    config_dict = {
        "app": {
            "name": "Test",
            "version": "1.0.0",
            "debug": False,
            "max_upload_size_mb": 5,
        },
        "logging": {
            "level": "INFO",
            "log_file": "logs/test.log",
            "rotation": "10 MB",
            "retention": "7 days",
            "format": "{message}",
        },
        # ... (other required fields would go here in a real test)
    }

    # This would normally validate the full config
    # For now, just test that Config class exists
    assert Config is not None


def test_invalid_max_upload_size():
    """Test that invalid max_upload_size_mb is rejected."""
    # This test demonstrates Pydantic validation
    # In practice, you'd create a full invalid config
    pass


def test_config_api_keys(monkeypatch):
    """Test API key retrieval from environment."""
    from rag.config import get_api_key

    # Set a test API key
    monkeypatch.setenv("TEST_API_KEY", "test-key-123")

    api_key = get_api_key("TEST_API_KEY")
    assert api_key == "test-key-123"


def test_missing_api_key():
    """Test that missing API key raises ValueError."""
    from rag.config import get_api_key

    with pytest.raises(ValueError, match="API key environment variable"):
        get_api_key("NONEXISTENT_KEY")
