"""Indexing module for document loading, chunking, and embedding.

This module handles the ingestion pipeline:
1. Load documents from files (PDF, TXT, etc.)
2. Split into chunks
3. Embed for vector storage
"""

from backend.indexing.chunker import chunk_documents
from backend.indexing.embedder import HashEmbedder, HFEmbedder
from backend.indexing.loader import load_file

__all__ = ["load_file", "chunk_documents", "HashEmbedder", "HFEmbedder"]
