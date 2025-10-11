"""
Document upload endpoints.

Handles file uploads and document ingestion with async I/O.
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from loguru import logger

from rag.backend.loaders.factory import LoaderFactory
from rag.backend.preprocessing.cleaner import TextCleaner
from rag.backend.schemas import UploadResponse
from rag.config import Config

router = APIRouter(prefix="/upload", tags=["upload"])


async def process_upload(
    file: UploadFile,
    config: Config,
    loader_factory: LoaderFactory,
    text_cleaner: TextCleaner,
    text_splitter,
    vectorstore,
    rag_pipeline=None,  # Optional for warnings
) -> UploadResponse:
    """
    Process uploaded file: load, clean, split, and store.

    This is fully async because:
    1. File I/O for reading uploads (can be several MB)
    2. Document loading (PDF parsing, website fetching, OCR)
    3. Embedding generation (API calls)
    4. Vector store writes (database I/O)

    A typical upload might involve:
    - File read: 100-500ms for multi-MB file
    - Document loading: 1-5 seconds for complex PDFs
    - Embedding: 2-10 seconds for API-based embeddings
    - DB writes: 0.5-2 seconds

    Total: 3.5-17.5 seconds of mostly I/O-bound operations.
    Without async, this would block all other requests!

    Includes fallback mode warnings when dummy models are active.

    Args:
        file: Uploaded file.
        config: Application configuration.
        loader_factory: Document loader factory.
        text_cleaner: Text cleaning preprocessor.
        text_splitter: Text splitter.
        vectorstore: Vector store.
        rag_pipeline: Optional RAG pipeline for warnings.

    Returns:
        Upload response with statistics and warnings.
    """
    # Check file size
    max_size_bytes = config.app.max_upload_size_mb * 1024 * 1024

    # Read file content (async I/O)
    content = await file.read()
    if len(content) > max_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {config.app.max_upload_size_mb}MB",
        )

    # Save to temporary file for processing
    filename_str = file.filename if file.filename else "upload"
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename_str).suffix) as tmp_file:
        tmp_file.write(content)
        tmp_path = tmp_file.name

    try:
        logger.info(f"Processing upload: {file.filename} ({len(content)} bytes)")

        # Step 1: Load document (async I/O for file reading, HTTP, OCR)
        loader = loader_factory.get_loader(tmp_path)
        documents = await loader.load(tmp_path)
        logger.info(f"Loaded {len(documents)} documents from {file.filename}")

        # Step 2: Clean text (CPU-bound, sync)
        if config.preprocessing.enabled and config.preprocessing.cleaning:
            documents = text_cleaner.process(documents)

        # Step 3: Split into chunks (CPU-bound, sync)
        chunks = text_splitter.split_documents(documents)
        logger.info(f"Split into {len(chunks)} chunks")

        # Step 4: Add to vector store (async I/O for embeddings + DB)
        doc_ids = await vectorstore.add_documents(chunks)
        logger.info(f"Added {len(doc_ids)} chunks to vector store")

        # Get warnings from pipeline (fallback mode notifications)
        warnings = rag_pipeline.get_warnings() if rag_pipeline else None

        if warnings:
            logger.info(f"Upload completed with {len(warnings)} warnings: {warnings}")

        return UploadResponse(
            message=f"Successfully processed {file.filename}",
            num_documents=len(documents),
            num_chunks=len(chunks),
            document_ids=doc_ids,
            warnings=warnings if warnings else None,
        )

    finally:
        # Clean up temporary file
        Path(tmp_path).unlink(missing_ok=True)


# This function will be completed in the main app file
