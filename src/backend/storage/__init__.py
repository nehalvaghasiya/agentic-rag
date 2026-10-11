"""Storage module for vector stores and knowledge base persistence.

This module handles:
1. Vector storage and similarity search
2. Knowledge base manifest and file management
"""

from backend.storage.kb import KBStore
from backend.storage.vector import VectorStore

__all__ = ["VectorStore", "KBStore"]
