"""Deterministic repository adapter; dictionary storage is confined to this test adapter."""

import copy
import hashlib
import json
import math
import time
from dataclasses import asdict
from typing import Any

from agentic_rag.data.answers import (
    choose_version,
    context_messages,
    finish_answer,
    normalize_messages,
    prepare_answer,
)
from agentic_rag.data.fake import FakeStore
from agentic_rag.data.repository import ConflictError, ContentUnavailableError
from agentic_rag.models.chunk import Chunk
from agentic_rag.models.document import Document
from agentic_rag.models.event import Event
from agentic_rag.models.evidence import Evidence
from agentic_rag.models.job import Job
from agentic_rag.models.principal import Principal
from agentic_rag.models.run import Run

TERMINAL = {"completed", "failed", "cancelled"}


class MemoryRepository:
    def __init__(self, store: FakeStore) -> None:
        self.store = store
        self.states: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self.fingerprints: dict[str, str] = {}
        self.models: dict[str, str] = {}

    async def open(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def create_kb(self, name: str, p: Principal, kb_id: str | None = None) -> dict[str, Any]:
        return self.store.create_kb(name, p, kb_id)

    async def check_kb(self, kb_id: str, p: Principal) -> dict[str, Any]:
        return self.store.check_kb(kb_id, p)

    async def list_kbs(self, p: Principal) -> list[dict[str, Any]]:
        return self.store.list_kbs(p)

    async def delete_kb(self, kb_id: str, p: Principal) -> None:
        async with self.store.lock:
            self.store.check_kb(kb_id, p)
            for doc in self.store.list_docs(p, kb_id):
                self._delete_document(doc)
            del self.store.kbs[kb_id]
            self.models.pop(kb_id, None)

    async def get_doc(self, doc_id: str, p: Principal) -> Document:
        return self.store.get_doc(doc_id, p)

    async def original(self, doc_id: str, p: Principal) -> tuple[Document, bytes]:
        async with self.store.lock:
            doc = self.store.get_doc(doc_id, p)
            blob = self.store.blobs.get(doc_id)
            if blob is None:
                raise ContentUnavailableError()
            return copy.deepcopy(doc), blob

    async def list_docs(self, p: Principal, kb_id: str | None = None) -> list[Document]:
        return self.store.list_docs(p, kb_id)

    async def submit(self, doc: Document, blob: bytes, job: Job, p: Principal) -> None:
        async with self.store.lock:
            self.store.check_kb(doc.kb_id, p)
            self.store.docs[doc.id], self.store.blobs[doc.id], self.store.jobs[job.id] = (
                doc,
                blob,
                job,
            )

    def _remove_chunks(self, doc_id: str) -> None:
        for cid in [cid for cid, chunk in self.store.chunks.items() if chunk.document_id == doc_id]:
            self.store.chunks.pop(cid, None)
            self.store.vectors.pop(cid, None)

    def _delete_document(self, doc: Document) -> None:
        doc.status, doc.acl_version = "deleted", doc.acl_version + 1
        self._remove_chunks(doc.id)
        self.store.blobs.pop(doc.id, None)
        for job in self.store.jobs.values():
            if job.document_id == doc.id and job.status in {"queued", "running"}:
                job.status, job.error = "failed", "SourceDeleted"
        for key in list(self.states):
            if key[0] == doc.tenant_id and key[2] == "cache":
                del self.states[key]

    async def delete_doc(self, doc_id: str, p: Principal) -> None:
        async with self.store.lock:
            self._delete_document(self.store.get_doc(doc_id, p))

    async def claim_job(self, p: Principal) -> tuple[Job, Document, bytes] | None:
        async with self.store.lock:
            for job in self.store.jobs.values():
                if job.tenant_id != p.tenant_id or not (
                    job.status == "queued"
                    or (job.status == "running" and job.lease_until < time.time())
                ):
                    continue
                doc = self.store.docs.get(job.document_id)
                if not doc or doc.status == "deleted" or doc.kb_id not in self.store.kbs:
                    job.status, job.error = "failed", "SourceDeleted"
                    continue
                if doc.version != job.version or job.attempts >= 3:
                    job.status, job.error = (
                        "failed",
                        "LeaseExhausted" if job.attempts >= 3 else "RevisionSuperseded",
                    )
                    if doc.version == job.version:
                        doc.status = "failed"
                    continue
                job.status, job.attempts, job.lease_until = (
                    "running",
                    job.attempts + 1,
                    time.time() + 120,
                )
                return copy.deepcopy(job), copy.deepcopy(doc), self.store.blobs.get(doc.id, b"")
            return None

    async def publish(
        self,
        job: Job,
        doc: Document,
        chunks: list[Chunk],
        vectors: list[list[float]],
        model: str,
        p: Principal,
    ) -> None:
        async with self.store.lock:
            current = self.store.get_doc(doc.id, p)
            lease = self.store.jobs[job.id]
            if (
                current.version != job.version
                or lease.status != "running"
                or lease.attempts != job.attempts
            ):
                raise ValueError("Document changed during ingestion")
            if len(chunks) != len(vectors) or not vectors or len({len(v) for v in vectors}) != 1:
                raise ValueError("Embedding count or dimensions mismatch")
            self._remove_chunks(doc.id)
            for chunk, vector in zip(chunks, vectors, strict=True):
                self.store.chunks[chunk.id], self.store.vectors[chunk.id] = chunk, vector
            current.status, lease.status, job.status = "ready", "done", "done"
            self.models[doc.kb_id] = f"{model}:{len(vectors[0])}"

    async def fail_job(self, job: Job, error: str, p: Principal) -> None:
        async with self.store.lock:
            current = self.store.jobs[job.id]
            if (
                current.tenant_id != p.tenant_id
                or current.status != "running"
                or current.attempts != job.attempts
            ):
                return
            current.status, current.error = "failed", error
            doc = self.store.docs[job.document_id]
            if doc.version == job.version and doc.status != "deleted":
                doc.status = "failed"

    async def get_job(self, job_id: str, p: Principal) -> Job:
        job = self.store.jobs.get(job_id)
        if not job or job.tenant_id != p.tenant_id:
            raise PermissionError("Job unavailable")
        return job

    async def dense(
        self, vector: list[float], kb_ids: tuple[str, ...], p: Principal, limit: int
    ) -> list[Evidence]:
        if not kb_ids:
            return []
        results = []
        for chunk in self.store.allowed_chunks(p, kb_ids):
            other = self.store.vectors[chunk.id]
            if len(other) != len(vector):
                raise ValueError("Embedding model dimensions changed; reingest this knowledge base")
            denom = math.sqrt(sum(x * x for x in vector) * sum(x * x for x in other))
            score = sum(a * b for a, b in zip(vector, other, strict=True)) / denom if denom else 0
            if score > 0:
                results.append(self.store.evidence(chunk, score))
        return sorted(results, key=lambda e: (-e.score, e.chunk_id))[:limit]

    async def keyword(
        self, text: str, kb_ids: tuple[str, ...], p: Principal, limit: int
    ) -> list[Evidence]:
        from agentic_rag.search.keyword import tokens

        if not kb_ids:
            return []
        words = set(tokens(text))
        results = [
            self.store.evidence(c, len(words.intersection(tokens(c.text))))
            for c in self.store.allowed_chunks(p, kb_ids)
        ]
        return sorted((e for e in results if e.score > 0), key=lambda e: (-e.score, e.chunk_id))[
            :limit
        ]

    async def evidence(self, ids: list[str], p: Principal) -> list[Evidence]:
        return self.store.get_evidence(ids, p)

    async def document_chunks(
        self, doc_id: str, p: Principal, limit: int = 512
    ) -> tuple[list[Evidence], int]:
        doc = self.store.get_doc(doc_id, p)
        if doc.status != "ready":
            return [], 0
        chunks = sorted(
            (
                c
                for c in self.store.allowed_chunks(p, (doc.kb_id,))
                if c.document_id == doc_id and c.version == doc.version
            ),
            key=lambda c: c.ordinal,
        )
        return [self.store.evidence(c, 1.0) for c in chunks[:limit]], len(chunks)

    async def revision(self, kb_ids: tuple[str, ...], p: Principal) -> str:
        docs = [asdict(d) for kb in kb_ids for d in self.store.list_docs(p, kb)]
        return hashlib.sha256(
            json.dumps([docs, self.models], sort_keys=True, default=sorted).encode()
        ).hexdigest()

    async def create_session(self, data: dict[str, Any], p: Principal) -> dict[str, Any]:
        self.store.sessions[data["id"]] = copy.deepcopy(data)
        return data

    async def get_session(self, uid: str, p: Principal) -> dict[str, Any]:
        data = self.store.sessions.get(uid)
        if not data or data["tenant"] != p.tenant_id or data["user"] != p.user_id:
            raise PermissionError("Session unavailable")
        session = copy.deepcopy(data)
        normalize_messages(session["messages"])
        return session

    async def list_sessions(self, p: Principal) -> list[dict[str, Any]]:
        return [
            {**copy.deepcopy(s), "messages": [], "summary": ""}
            for s in self.store.sessions.values()
            if s["tenant"] == p.tenant_id and s["user"] == p.user_id
        ]

    async def context_session(self, uid: str, p: Principal) -> dict[str, Any]:
        session = await self.get_session(uid, p)
        session["messages"] = context_messages(session["messages"])[-16:]
        return session

    async def save_session(self, data: dict[str, Any], p: Principal) -> None:
        current = await self.get_session(data["id"], p)
        current.update(
            {k: v for k, v in data.items() if k not in {"messages", "active_run_id", "updated_at"}}
        )
        self.store.sessions[data["id"]] = copy.deepcopy(current)

    async def delete_session(self, uid: str, p: Principal) -> None:
        await self.get_session(uid, p)
        del self.store.sessions[uid]
        for run_id in [r.id for r in self.store.runs.values() if r.session_id == uid]:
            self.store.runs.pop(run_id)
            self.store.events.pop(run_id, None)
        for key in list(self.states):
            if key[:2] == (p.tenant_id, p.user_id) and (
                self.states[key].get("session_id") == uid or key[2] == "cache"
            ):
                del self.states[key]

    async def begin_run(
        self, run: Run, message: dict[str, Any] | None, fingerprint: str, p: Principal
    ) -> tuple[Run, bool]:
        async with self.store.lock:
            if run.client_message_id:
                for old in self.store.runs.values():
                    if (old.tenant_id, old.user_id, old.client_message_id) == (
                        p.tenant_id,
                        p.user_id,
                        run.client_message_id,
                    ):
                        if self.fingerprints.get(old.id) != fingerprint:
                            raise ConflictError(
                                "Message ID was already used for a different request"
                            )
                        return copy.deepcopy(old), False
            if run.session_id:
                session = await self.get_session(run.session_id, p)
                if any(
                    r.session_id == run.session_id and r.status not in TERMINAL
                    for r in self.store.runs.values()
                ):
                    raise ConflictError("This chat already has a running response")
                prepare_answer(session, run, message)
                if message:
                    session["title"] = (
                        str(message["content"])[:32]
                        if session["title"] == "New chat"
                        else session["title"]
                    )
                    session["updated_at"] = run.created_at
                session["active_run_id"] = run.id
                self.store.sessions[run.session_id] = session
            run.answer = ""
            self.store.runs[run.id] = copy.deepcopy(run)
            self.fingerprints[run.id] = fingerprint
            return run, True

    async def get_run(self, uid: str, p: Principal) -> Run:
        return copy.deepcopy(self.store.run_for(uid, p))

    async def save_run(self, run: Run, p: Principal) -> None:
        old = await self.get_run(run.id, p)
        if old.status not in TERMINAL:
            self.store.runs[run.id] = copy.deepcopy(run)

    async def finish(self, run: Run, kind: str, data: dict[str, Any], p: Principal) -> bool:
        async with self.store.lock:
            old = await self.get_run(run.id, p)
            if old.status in TERMINAL:
                return False
            self.store.runs[run.id] = copy.deepcopy(run)
            await self.log(run.id, kind, data, p)
            if run.session_id and run.session_id in self.store.sessions:
                session = self.store.sessions[run.session_id]
                session["active_run_id"] = None
                session["updated_at"] = data.get("finished_at", run.created_at)
                finish_answer(session, run, session["updated_at"])
            return True

    async def select_version(
        self, uid: str, message_id: str, run_id: str, expected: str, p: Principal
    ) -> dict[str, Any]:
        async with self.store.lock:
            session = await self.get_session(uid, p)
            run = await self.get_run(run_id, p)
            answer = choose_version(session, message_id, run, expected)
            self.store.sessions[uid] = copy.deepcopy(session)
            return copy.deepcopy(answer)

    async def log(self, run_id: str, kind: str, data: dict[str, Any], p: Principal) -> Event:
        run = self.store.run_for(run_id, p)
        if run.status in TERMINAL and kind not in {"complete", "error", "cancelled"}:
            return self.store.events[run_id][-1]
        return self.store.log(run_id, kind, data)

    async def events(self, run_id: str, p: Principal, after: int = 0) -> list[Event]:
        self.store.run_for(run_id, p)
        return [e for e in self.store.events.get(run_id, []) if e.id > after]

    async def audit(self, data: dict[str, Any], p: Principal) -> None:
        self.store.audit.append({**data, "tenant": p.tenant_id, "user": p.user_id})

    async def state_get(self, namespace: str, key: str, p: Principal) -> dict[str, Any] | None:
        return copy.deepcopy(self.states.get((p.tenant_id, p.user_id, namespace, key)))

    async def state_put(
        self, namespace: str, key: str, value: dict[str, Any], p: Principal
    ) -> None:
        self.states[p.tenant_id, p.user_id, namespace, key] = copy.deepcopy(value)

    async def state_delete(self, namespace: str, key: str, p: Principal) -> None:
        self.states.pop((p.tenant_id, p.user_id, namespace, key), None)

    async def state_list(self, namespace: str, p: Principal) -> list[dict[str, Any]]:
        return [
            copy.deepcopy(v)
            for k, v in self.states.items()
            if k[:3] == (p.tenant_id, p.user_id, namespace)
        ]

    async def ingest_metrics(self, p: Principal) -> dict[str, float | None]:
        from agentic_rag.eval.ingest import IngestMetrics

        return IngestMetrics().score(self.store)
