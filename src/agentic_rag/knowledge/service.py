"""Authorized document lifecycle through the shared persistence boundary."""

import asyncio
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from agentic_rag.data.repository import ConflictError, Repository
from agentic_rag.knowledge.parser import ParserRegistry
from agentic_rag.memory.conversation import now
from agentic_rag.models.document import Document
from agentic_rag.models.job import Job
from agentic_rag.models.principal import Principal
from agentic_rag.models.upload import Upload


class KnowledgeService:
    def __init__(self, store: Repository) -> None:
        self.store = store
        self.parser = ParserRegistry()

    async def create_kb(
        self, name: str, principal: Principal, kb_id: str | None = None
    ) -> dict[str, Any]:
        if not name.strip() or len(name) > 100:
            raise ValueError("Invalid knowledge base name")
        return await self.store.create_kb(name.strip(), principal, kb_id)

    async def submit(self, files: list[Upload], kb_id: str, principal: Principal) -> list[Job]:
        await self.store.check_kb(kb_id, principal)
        for file in files:
            self.parser.parse(file)
        jobs = []
        for file in files:
            uid = uuid4().hex
            doc = Document(
                uid,
                kb_id,
                principal.tenant_id,
                file.filename,
                file.content_type or "text/plain",
                owner=principal.user_id,
                size=len(file.content),
                created_at=now(),
                updated_at=now(),
            )
            job = Job(uuid4().hex, principal.tenant_id, kb_id, uid, created_at=now())
            await self.store.submit(doc, file.content, job, principal)
            jobs.append(job)
        return jobs

    async def update(self, doc_id: str, file: Upload, principal: Principal) -> Job:
        doc = await self.store.get_doc(doc_id, principal)
        if doc.owner != principal.user_id and "admin" not in principal.roles:
            raise PermissionError("Cannot modify someone else's document")
        self.parser.parse(file)
        doc.title, doc.version, doc.acl_version = (
            file.filename,
            doc.version + 1,
            doc.acl_version + 1,
        )
        doc.status, doc.size, doc.updated_at = "processing", len(file.content), now()
        job = Job(
            uuid4().hex,
            principal.tenant_id,
            doc.kb_id,
            doc.id,
            created_at=now(),
            version=doc.version,
        )
        await self.store.submit(doc, file.content, job, principal)
        return job

    async def delete(self, doc_id: str, principal: Principal) -> None:
        doc = await self.store.get_doc(doc_id, principal)
        if doc.owner != principal.user_id and "admin" not in principal.roles:
            raise PermissionError("Cannot delete someone else's document")
        await self.store.delete_doc(doc_id, principal)
        await self.store.audit({"action": "delete", "document": doc_id}, principal)

    async def status(self, job_id: str, principal: Principal) -> Job:
        return await self.store.get_job(job_id, principal)

    async def list_docs(self, kb_id: str, principal: Principal) -> list[dict[str, object]]:
        return [
            {
                **asdict(doc),
                "can_delete": doc.owner == principal.user_id or "admin" in principal.roles,
            }
            for doc in await self.store.list_docs(principal, kb_id)
        ]

    async def original(
        self, doc_id: str, principal: Principal, version: int | None = None
    ) -> tuple[Document, bytes]:
        doc, content = await self.store.original(doc_id, principal)
        if version is not None and doc.version != version:
            raise ConflictError("The document changed. Refresh it before trying again.")
        return doc, content

    async def preview(
        self,
        doc_id: str,
        principal: Principal,
        offset: int = 0,
        limit: int = 20_000,
        version: int | None = None,
    ) -> dict[str, Any]:
        doc, content = await self.original(doc_id, principal, version)
        sections = await asyncio.to_thread(
            self.parser.parse, Upload(doc.title, content, doc.content_type)
        )
        total = sum(len(text) for text, _, _ in sections)
        result = []
        position = 0
        for text, page, section in sections:
            start, end = max(0, offset - position), min(len(text), offset + limit - position)
            if start < end:
                result.append({"text": text[start:end], "page": page, "section": section})
            position += len(text)
        # Parsing runs in a thread: reauthorize before returning extracted content.
        current = await self.store.get_doc(doc_id, principal)
        if current.version != doc.version:
            raise ConflictError("The document changed. Refresh it before trying again.")
        return {
            "document_id": doc.id,
            "version": doc.version,
            "title": doc.title,
            "offset": offset,
            "total_characters": total,
            "sections": result,
            "next_offset": offset + limit if offset + limit < total else None,
        }

    async def delete_kb(self, kb_id: str, principal: Principal) -> None:
        if "admin" not in principal.roles:
            raise PermissionError("KB deletion requires admin role")
        await self.store.delete_kb(kb_id, principal)
        await self.store.audit({"action": "delete_kb", "knowledge_base": kb_id}, principal)
