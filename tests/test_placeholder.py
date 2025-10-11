# Placeholder for an empty build.
"""
Placeholder tests for Agentic RAG.

This file contains basic tests to verify the project structure.
See test_config.py and test_loaders.py for more comprehensive tests.
"""

import pytest


def test_imports():
    """Test that core modules can be imported."""
    from rag import __version__
    from rag.config import load_config

    assert __version__ is not None


def test_package_structure():
    """Test that package structure is correct."""
    import rag.backend.loaders
    import rag.backend.embeddings
    import rag.backend.vectorstore
    import rag.backend.llm

    # If imports work, structure is correct
    assert True
