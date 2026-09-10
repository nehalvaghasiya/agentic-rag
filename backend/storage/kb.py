"""Knowledge base storage and management.

Handles knowledge base creation, persistence, and retrieval.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from fastapi import UploadFile

from backend.indexing import chunk_documents, load_file
from backend.models import DocumentMeta, KBManifest, KnowledgeBase
from backend.storage.vector import VectorStore

if TYPE_CHECKING:
    from backend.config import Settings


class KBStore:
    """Manages knowledge bases on disk.

    Handles creation, listing, and loading of knowledge bases
    with their associated vector stores.
    """

    def __init__(self, data_dir: Path):
        """Initialize the KB store.

        Args:
            data_dir: Root directory for data storage.
        """
        self._root = data_dir / "kbs"
        self._uploads = data_dir / "uploads"
        self._root.mkdir(parents=True, exist_ok=True)
        self._uploads.mkdir(parents=True, exist_ok=True)

    def list_all(self) -> list[KnowledgeBase]:
        """List all knowledge bases.

        Returns:
            List of knowledge base summaries.
        """
        kbs = []
        for manifest_path in self._root.glob("*/manifest.json"):
            try:
                manifest = self._load_manifest(manifest_path)
                kbs.append(self._to_api(manifest))
            except Exception:
                # Skip invalid manifests
                continue
        return kbs

    async def create(
        self,
        name: str,
        embedding_model: str,
        files: list[UploadFile],
        settings: Settings,
    ) -> KnowledgeBase:
        """Create a new knowledge base.

        Args:
            name: Knowledge base name.
            embedding_model: Model to use for embeddings.
            files: Uploaded files to index.
            settings: Application settings.

        Returns:
            Created knowledge base summary.
        """
        from backend.llm import get_embedder

        # Generate unique ID
        kb_id = f"kb_{uuid4().hex}"
        kb_dir = self._root / kb_id
        kb_dir.mkdir(parents=True, exist_ok=True)

        upload_dir = self._uploads / kb_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Load and process documents
        all_docs = []
        doc_metas = []

        for f in files:
            content = await f.read()
            file_path = upload_dir / f.filename

            # Load file into documents
            docs = load_file(file_path, content)
            all_docs.extend(docs)

            # Track metadata
            suffix = file_path.suffix.lower().lstrip(".")
            doc_metas.append(
                DocumentMeta(
                    id=f"doc_{f.filename}",
                    name=f.filename,
                    type=suffix or "txt",
                    size=len(content),
                    uploaded_at=datetime.now(),
                )
            )

        # Chunk documents
        chunks = chunk_documents(
            all_docs,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

        # Embed and store
        embedder = get_embedder(embedding_model, settings)
        store = VectorStore(embedder)
        store.add(chunks)
        store.save(kb_dir / "vectors.pkl")

        # Save manifest
        manifest = KBManifest(
            id=kb_id,
            name=name,
            embedding_model=embedding_model,
            created_at=datetime.now(),
            documents=doc_metas,
        )
        self._save_manifest(kb_dir / "manifest.json", manifest)

        return self._to_api(manifest)

    def load(self, kb_id: str, settings: Settings) -> tuple[KBManifest, VectorStore] | None:
        """Load a knowledge base by ID.

        Args:
            kb_id: Knowledge base ID.
            settings: Application settings.

        Returns:
            Tuple of (manifest, vector_store), or None if not found.
        """
        from backend.llm import get_embedder

        manifest_path = self._root / kb_id / "manifest.json"
        if not manifest_path.exists():
            return None

        manifest = self._load_manifest(manifest_path)
        embedder = get_embedder(manifest.embedding_model, settings)
        store = VectorStore.load(self._root / kb_id / "vectors.pkl", embedder)

        return manifest, store

    def exists(self, kb_id: str) -> bool:
        """Check if a knowledge base exists.

        Args:
            kb_id: Knowledge base ID.

        Returns:
            True if the knowledge base exists.
        """
        return (self._root / kb_id / "manifest.json").exists()

    def _load_manifest(self, path: Path) -> KBManifest:
        """Load a manifest from disk."""
        return KBManifest.model_validate_json(path.read_text())

    def _save_manifest(self, path: Path, manifest: KBManifest) -> None:
        """Save a manifest to disk."""
        path.write_text(manifest.model_dump_json(indent=2))

    def _to_api(self, manifest: KBManifest) -> KnowledgeBase:
        """Convert manifest to API response model."""
        # Find most recent document upload time for last_modified
        last_modified = manifest.created_at
        if manifest.documents:
            latest_doc = max(manifest.documents, key=lambda d: d.uploaded_at)
            last_modified = latest_doc.uploaded_at

        return KnowledgeBase(
            id=manifest.id,
            name=manifest.name,
            embedding_model=manifest.embedding_model,
            created_at=manifest.created_at,
            file_count=len(manifest.documents),
            total_size=sum(d.size for d in manifest.documents),
            documents=manifest.documents,
            chunking_strategy="Recursive (800/120)",
            ranking_strategy="Hybrid",
            last_modified=last_modified,
        )


__all__ = ["KBStore"]
