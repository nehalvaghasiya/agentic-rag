"""Deterministic tenant-aware in-memory adapter for demos and unit tests.

Not a production persistence layer; no data survives process restart.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from agentic_rag.models.chunk import Chunk
from agentic_rag.models.document import Document
from agentic_rag.models.event import Event
from agentic_rag.models.evidence import Evidence
from agentic_rag.models.job import Job
from agentic_rag.models.principal import Principal
from agentic_rag.models.run import Run


class FakeStore:
    """One shared store for authorized demo operations and reproducible evaluation."""

    def __init__(self) -> None:
        self.kbs: dict[str, dict[str, str]] = {}
        self.docs: dict[str, Document] = {}
        self.chunks: dict[str, Chunk] = {}
        self.vectors: dict[str, list[float]] = {}
        self.blobs: dict[str, bytes] = {}
        self.jobs: dict[str, Job] = {}
        self.events: dict[str, list[Event]] = {}
        self.runs: dict[str, Run] = {}
        self.sessions: dict[str, dict[str, Any]] = {}
        self.audit: list[dict[str, object]] = []
        self.memories: dict[str, dict[str, Any]] = {}
        self.consent: set[tuple[str, str]] = set()
        self.receipts: dict[tuple[str, str], dict[str, object]] = {}
        self.lock = asyncio.Lock()

    def create_kb(
        self, name: str, principal: Principal, kb_id: str | None = None
    ) -> dict[str, str]:
        uid = kb_id or uuid4().hex
        if uid in self.kbs:
            raise ValueError("Knowledge base already exists")
        kb = {
            "id": uid,
            "name": name,
            "tenant_id": principal.tenant_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.kbs[uid] = kb
        return kb

    def check_kb(self, kb_id: str, principal: Principal) -> dict[str, str]:
        kb = self.kbs.get(kb_id)
        if kb is None or kb["tenant_id"] != principal.tenant_id:
            raise PermissionError("Knowledge base unavailable")
        return kb

    def list_kbs(self, principal: Principal) -> list[dict[str, str]]:
        return [kb for kb in self.kbs.values() if kb["tenant_id"] == principal.tenant_id]

    def get_doc(self, doc_id: str, principal: Principal) -> Document:
        doc = self.docs.get(doc_id)
        if doc is None or not self.allowed(doc, principal):
            raise PermissionError("Document unavailable")
        return doc

    def allowed(self, doc: Document, principal: Principal) -> bool:
        return bool(
            doc.tenant_id == principal.tenant_id
            and doc.status != "deleted"
            and (
                not doc.groups
                or bool(doc.groups.intersection(principal.groups))
                or doc.owner == principal.user_id
                or "admin" in principal.roles
            )
        )

    def list_docs(self, principal: Principal, kb_id: str | None = None) -> list[Document]:
        if kb_id:
            self.check_kb(kb_id, principal)
        return [
            d
            for d in self.docs.values()
            if self.allowed(d, principal) and (not kb_id or d.kb_id == kb_id)
        ]

    async def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Embedding count mismatch")
        async with self.lock:
            for chunk, vector in zip(chunks, vectors, strict=True):
                self.chunks[chunk.id] = chunk
                self.vectors[chunk.id] = vector

    async def remove(self, doc_id: str, principal: Principal) -> None:
        self.get_doc(doc_id, principal)
        async with self.lock:
            for cid in [k for k, c in self.chunks.items() if c.document_id == doc_id]:
                self.chunks.pop(cid, None)
                self.vectors.pop(cid, None)

    def allowed_chunks(self, principal: Principal, kb_ids: tuple[str, ...]) -> list[Chunk]:
        for kb in kb_ids:
            self.check_kb(kb, principal)
        return [
            c
            for c in self.chunks.values()
            if (not kb_ids or c.kb_id in kb_ids)
            and (doc := self.docs.get(c.document_id)) is not None
            and self.allowed(doc, principal)
            and doc.version == c.version
            and doc.status == "ready"
        ]

    def evidence(self, chunk: Chunk, score: float) -> Evidence:
        doc = self.docs[chunk.document_id]
        return Evidence(
            chunk_id=chunk.id,
            document_id=doc.id,
            version=chunk.version,
            text=chunk.text,
            score=score,
            source_uri=doc.source_uri,
            page=chunk.page,
            section=chunk.section,
            tenant_id=doc.tenant_id,
            acl_version=doc.acl_version,
            title=doc.title,
        )

    def get_evidence(self, ids: list[str], principal: Principal) -> list[Evidence]:
        found: list[Evidence] = []
        for uid in ids:
            chunk = self.chunks.get(uid)
            if chunk is None:
                continue
            doc = self.docs.get(chunk.document_id)
            if (
                doc
                and self.allowed(doc, principal)
                and doc.version == chunk.version
                and doc.status == "ready"
            ):
                found.append(self.evidence(chunk, 1.0))
        return found

    def log(self, run_id: str, kind: str, data: dict[str, object]) -> Event:
        events = self.events.setdefault(run_id, [])
        event = Event(len(events) + 1, run_id, kind, data)
        events.append(event)
        return event

    def run_for(self, run_id: str, principal: Principal) -> Run:
        run = self.runs.get(run_id)
        if run is None or run.tenant_id != principal.tenant_id or run.user_id != principal.user_id:
            raise PermissionError("Run unavailable")
        return run

    async def remove_deleted(self, doc_id: str) -> None:
        """Remove all indexed evidence after a tombstone is committed."""
        async with self.lock:
            for cid in [k for k, c in self.chunks.items() if c.document_id == doc_id]:
                self.chunks.pop(cid, None)
                self.vectors.pop(cid, None)
