"""PostgreSQL repositories. No process-local mirror or pickle deserialization."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from psycopg import AsyncConnection
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from agentic_rag.data.answers import (
    choose_version,
    context_messages,
    finish_answer,
    normalize_messages,
    prepare_answer,
)
from agentic_rag.data.memory import TERMINAL
from agentic_rag.data.repository import ConflictError, ContentUnavailableError
from agentic_rag.models.chunk import Chunk
from agentic_rag.models.document import Document
from agentic_rag.models.event import Event
from agentic_rag.models.evidence import Evidence
from agentic_rag.models.job import Job
from agentic_rag.models.principal import Principal
from agentic_rag.models.run import Run


def js(value: Any) -> Jsonb:
    return Jsonb(
        json.loads(
            json.dumps(
                value, default=lambda x: sorted(x) if isinstance(x, (set, frozenset)) else str(x)
            )
        )
    )


class PostgresRepository:
    def __init__(self, url: str) -> None:
        self.pool: AsyncConnectionPool[AsyncConnection[dict[str, Any]]] = AsyncConnectionPool(
            url, open=False, min_size=1, max_size=8, kwargs={"row_factory": dict_row}
        )

    async def open(self) -> None:
        await self.pool.open(wait=True, timeout=15)
        async with self.pool.connection() as conn:
            role = await (
                await conn.execute(
                    "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
                )
            ).fetchone()
            if role and (role["rolsuper"] or role["rolbypassrls"]):
                raise ValueError(
                    "Application database role must be NOSUPERUSER NOBYPASSRLS; run agentic-rag migrate with separate admin and application URLs"
                )
            row = await (
                await conn.execute("SELECT max(version) AS version FROM rag.schema_version")
            ).fetchone()
            if not row or row["version"] != 3:
                raise ValueError("Database migration required: run agentic-rag migrate")

    async def close(self) -> None:
        await self.pool.close()

    @asynccontextmanager
    async def transaction(self, p: Principal) -> AsyncIterator[AsyncConnection[dict[str, Any]]]:
        async with self.pool.connection() as conn, conn.transaction():
            await conn.execute(
                "SELECT set_config('app.tenant_id',%s,true),set_config('app.user_id',%s,true),set_config('app.roles',%s,true),set_config('app.groups',%s,true)",
                (p.tenant_id, p.user_id, json.dumps(sorted(p.roles)), json.dumps(sorted(p.groups))),
            )
            yield conn

    async def create_kb(self, name: str, p: Principal, kb_id: str | None = None) -> dict[str, Any]:
        async with self.transaction(p) as conn:
            row = await (
                await conn.execute(
                    "INSERT INTO rag.knowledge(id,tenant_id,name) VALUES(%s,%s,%s) RETURNING id,tenant_id,name,revision,embedding_model,dimensions,created_at::text",
                    (kb_id or uuid4().hex, p.tenant_id, name),
                )
            ).fetchone()
            assert row is not None
            return row

    async def check_kb(self, kb_id: str, p: Principal) -> dict[str, Any]:
        async with self.transaction(p) as conn:
            row = await (
                await conn.execute(
                    "SELECT id,tenant_id,name,revision,embedding_model,dimensions,created_at::text FROM rag.knowledge WHERE id=%s AND NOT deleted",
                    (kb_id,),
                )
            ).fetchone()
            if not row:
                raise PermissionError("Knowledge base unavailable")
            return row

    async def list_kbs(self, p: Principal) -> list[dict[str, Any]]:
        async with self.transaction(p) as conn:
            return await (
                await conn.execute(
                    "SELECT id,tenant_id,name,revision,embedding_model,dimensions,created_at::text FROM rag.knowledge WHERE NOT deleted ORDER BY created_at DESC"
                )
            ).fetchall()

    async def delete_kb(self, kb_id: str, p: Principal) -> None:
        await self.check_kb(kb_id, p)
        async with self.transaction(p) as conn:
            await conn.execute("SELECT id FROM rag.knowledge WHERE id=%s FOR UPDATE", (kb_id,))
            await conn.execute("DELETE FROM rag.chunks WHERE kb_id=%s", (kb_id,))
            await conn.execute(
                "DELETE FROM rag.contents WHERE document_id IN (SELECT id FROM rag.documents WHERE kb_id=%s)",
                (kb_id,),
            )
            await conn.execute(
                "UPDATE rag.jobs SET status='failed',error='SourceDeleted',data=data || '{\"status\":\"failed\",\"error\":\"SourceDeleted\"}'::jsonb WHERE status IN ('queued','running') AND document_id IN (SELECT id FROM rag.documents WHERE kb_id=%s)",
                (kb_id,),
            )
            await conn.execute(
                "UPDATE rag.documents SET status='deleted',acl_version=acl_version+1 WHERE kb_id=%s",
                (kb_id,),
            )
            await conn.execute(
                "UPDATE rag.knowledge SET deleted=true,revision=revision+1 WHERE id=%s", (kb_id,)
            )
            await conn.execute("DELETE FROM rag.user_state WHERE namespace='cache'")

    @staticmethod
    def document(row: dict[str, Any]) -> Document:
        data = row["data"]
        return Document(
            id=row["id"],
            kb_id=row["kb_id"],
            tenant_id=row["tenant_id"],
            title=row["title"],
            content_type=row["content_type"],
            version=row["version"],
            status=row["status"],
            owner=row["owner_id"],
            groups=frozenset(row["groups"]),
            source_uri=row["source_uri"],
            acl_version=row["acl_version"],
            size=data.get("size", 0),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    async def get_doc(self, doc_id: str, p: Principal) -> Document:
        async with self.transaction(p) as conn:
            row = await (
                await conn.execute(
                    "SELECT * FROM rag.documents WHERE id=%s AND status<>'deleted'", (doc_id,)
                )
            ).fetchone()
            if not row:
                raise PermissionError("Document unavailable")
            return self.document(row)

    async def original(self, doc_id: str, p: Principal) -> tuple[Document, bytes]:
        async with self.transaction(p) as conn:
            row = await (
                await conn.execute(
                    "SELECT d.*,c.content,c.version AS content_version FROM rag.documents d LEFT JOIN rag.contents c ON c.document_id=d.id WHERE d.id=%s AND d.status<>'deleted'",
                    (doc_id,),
                )
            ).fetchone()
            if not row:
                raise PermissionError("Document unavailable")
            if row["content"] is None:
                raise ContentUnavailableError()
            if row["content_version"] != row["version"]:
                raise ConflictError("The document changed. Refresh it before trying again.")
            return self.document(row), bytes(row["content"])

    async def list_docs(self, p: Principal, kb_id: str | None = None) -> list[Document]:
        if kb_id:
            await self.check_kb(kb_id, p)
        async with self.transaction(p) as conn:
            rows = await (
                await conn.execute(
                    "SELECT * FROM rag.documents WHERE status<>'deleted' AND (%s::text IS NULL OR kb_id=%s) ORDER BY modified_at",
                    (kb_id, kb_id),
                )
            ).fetchall()
            return [self.document(r) for r in rows]

    async def submit(self, doc: Document, blob: bytes, job: Job, p: Principal) -> None:
        await self.check_kb(doc.kb_id, p)
        async with self.transaction(p) as conn:
            active = await (
                await conn.execute(
                    "SELECT id FROM rag.knowledge WHERE id=%s AND NOT deleted FOR UPDATE",
                    (doc.kb_id,),
                )
            ).fetchone()
            if not active:
                raise PermissionError("Knowledge base unavailable")
            await conn.execute(
                """INSERT INTO rag.documents(id,tenant_id,kb_id,owner_id,groups,title,source_uri,content_type,version,acl_version,status,data)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO UPDATE SET
                title=EXCLUDED.title,content_type=EXCLUDED.content_type,version=EXCLUDED.version,
                acl_version=EXCLUDED.acl_version,status=EXCLUDED.status,data=EXCLUDED.data,modified_at=now()""",
                (
                    doc.id,
                    doc.tenant_id,
                    doc.kb_id,
                    doc.owner,
                    list(doc.groups),
                    doc.title,
                    doc.source_uri or f"kb://{doc.kb_id}/{doc.id}",
                    doc.content_type,
                    doc.version,
                    doc.acl_version,
                    doc.status,
                    js(asdict(doc)),
                ),
            )
            await conn.execute(
                "INSERT INTO rag.contents VALUES(%s,%s,%s,%s) ON CONFLICT(document_id) DO UPDATE SET version=EXCLUDED.version,content=EXCLUDED.content",
                (doc.id, p.tenant_id, doc.version, blob),
            )
            await conn.execute(
                "INSERT INTO rag.jobs(id,tenant_id,document_id,status,data) VALUES(%s,%s,%s,'queued',%s)",
                (job.id, p.tenant_id, doc.id, js(asdict(job))),
            )
            await conn.execute(
                "UPDATE rag.knowledge SET revision=revision+1 WHERE id=%s", (doc.kb_id,)
            )

    async def delete_doc(self, doc_id: str, p: Principal) -> None:
        doc = await self.get_doc(doc_id, p)
        async with self.transaction(p) as conn:
            await conn.execute("SELECT id FROM rag.knowledge WHERE id=%s FOR UPDATE", (doc.kb_id,))
            await conn.execute("SELECT id FROM rag.documents WHERE id=%s FOR UPDATE", (doc_id,))
            await conn.execute(
                "UPDATE rag.jobs SET status='failed',error='SourceDeleted',data=data || '{\"status\":\"failed\",\"error\":\"SourceDeleted\"}'::jsonb WHERE document_id=%s AND status IN ('queued','running')",
                (doc_id,),
            )
            await conn.execute("DELETE FROM rag.chunks WHERE document_id=%s", (doc_id,))
            await conn.execute("DELETE FROM rag.contents WHERE document_id=%s", (doc_id,))
            await conn.execute(
                "UPDATE rag.documents SET status='deleted',acl_version=acl_version+1 WHERE id=%s",
                (doc_id,),
            )
            await conn.execute(
                "UPDATE rag.knowledge SET revision=revision+1 WHERE id=%s", (doc.kb_id,)
            )
            await conn.execute("DELETE FROM rag.user_state WHERE namespace='cache'")

    async def claim_job(self, p: Principal) -> tuple[Job, Document, bytes] | None:
        while True:
            async with self.transaction(p) as conn:
                candidate = await (
                    await conn.execute(
                        "SELECT j.id,d.kb_id FROM rag.jobs j JOIN rag.documents d ON d.id=j.document_id JOIN rag.knowledge k ON k.id=d.kb_id WHERE NOT k.deleted AND d.status<>'deleted' AND (j.status='queued' OR (j.status='running' AND j.lease_until<now())) ORDER BY j.updated_at,j.id LIMIT 1"
                    )
                ).fetchone()
                if not candidate:
                    return None
                await conn.execute(
                    "SELECT id FROM rag.knowledge WHERE id=%s FOR UPDATE", (candidate["kb_id"],)
                )
                row = await (
                    await conn.execute(
                        "SELECT * FROM rag.jobs WHERE id=%s AND (status='queued' OR (status='running' AND lease_until<now())) FOR UPDATE SKIP LOCKED",
                        (candidate["id"],),
                    )
                ).fetchone()
                if not row:
                    continue
                job = Job(**row["data"])
                docrow = await (
                    await conn.execute(
                        "SELECT * FROM rag.documents WHERE id=%s",
                        (job.document_id,),
                    )
                ).fetchone()
                blob = await (
                    await conn.execute(
                        "SELECT content,version FROM rag.contents WHERE document_id=%s",
                        (job.document_id,),
                    )
                ).fetchone()
                error = None
                if not docrow or not blob:
                    error = "SourceDeleted"
                elif docrow["version"] != job.version or blob["version"] != job.version:
                    error = "RevisionSuperseded"
                elif row["attempts"] >= 3:
                    error = "LeaseExhausted"
                if error:
                    job.status, job.error, job.attempts = "failed", error, row["attempts"]
                    await conn.execute(
                        "UPDATE rag.jobs SET status='failed',error=%s,data=%s WHERE id=%s",
                        (error, js(asdict(job)), job.id),
                    )
                    await conn.execute(
                        "UPDATE rag.documents SET status='failed' WHERE id=%s AND version=%s",
                        (job.document_id, job.version),
                    )
                    continue
                job.status, job.attempts, job.lease_until = (
                    "running",
                    row["attempts"] + 1,
                    time.time() + 120,
                )
                await conn.execute(
                    "UPDATE rag.jobs SET status='running',attempts=%s,lease_until=now()+interval '120 seconds',data=%s WHERE id=%s",
                    (job.attempts, js(asdict(job)), job.id),
                )
                assert docrow is not None and blob is not None
                return job, self.document(docrow), bytes(blob["content"])

    async def publish(
        self,
        job: Job,
        doc: Document,
        chunks: list[Chunk],
        vectors: list[list[float]],
        model: str,
        p: Principal,
    ) -> None:
        if not vectors or len(vectors) != len(chunks) or len({len(v) for v in vectors}) != 1:
            raise ValueError("Embedding count or dimensions mismatch")
        dims = len(vectors[0])
        async with self.transaction(p) as conn:
            # Every ingestion/deletion mutation locks the base first, avoiding job/document deadlocks.
            kb = await (
                await conn.execute(
                    "SELECT dimensions,embedding_model FROM rag.knowledge WHERE id=%s AND NOT deleted FOR UPDATE",
                    (doc.kb_id,),
                )
            ).fetchone()
            if not kb:
                raise ValueError("Knowledge base was deleted during ingestion")
            lease = await (
                await conn.execute(
                    "SELECT status,attempts FROM rag.jobs WHERE id=%s FOR UPDATE", (job.id,)
                )
            ).fetchone()
            if not lease or lease["status"] != "running" or lease["attempts"] != job.attempts:
                raise ValueError("Ingestion lease was superseded")
            current = await (
                await conn.execute(
                    "SELECT version FROM rag.documents WHERE id=%s AND status<>'deleted' FOR UPDATE",
                    (doc.id,),
                )
            ).fetchone()
            if not current or current["version"] != job.version:
                raise ValueError("Document changed during ingestion")
            if (
                kb
                and kb["dimensions"]
                and (kb["dimensions"] != dims or kb["embedding_model"] != model)
            ):
                raise ValueError(
                    "Embedding model changed; create a new knowledge base and reingest"
                )
            await conn.execute("DELETE FROM rag.chunks WHERE document_id=%s", (doc.id,))
            for chunk, vector in zip(chunks, vectors, strict=True):
                await conn.execute(
                    "INSERT INTO rag.chunks(id,tenant_id,kb_id,document_id,version,page,section,text,embedding,data) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::vector,%s)",
                    (
                        chunk.id,
                        p.tenant_id,
                        doc.kb_id,
                        doc.id,
                        doc.version,
                        chunk.page,
                        chunk.section,
                        chunk.text,
                        json.dumps(vector),
                        js(asdict(chunk)),
                    ),
                )
            await conn.execute("UPDATE rag.documents SET status='ready' WHERE id=%s", (doc.id,))
            job.status = "done"
            await conn.execute(
                "UPDATE rag.jobs SET status='done',data=%s WHERE id=%s", (js(asdict(job)), job.id)
            )
            await conn.execute(
                "UPDATE rag.knowledge SET revision=revision+1,embedding_model=%s,dimensions=%s WHERE id=%s",
                (model, dims, doc.kb_id),
            )
            await conn.execute("DELETE FROM rag.user_state WHERE namespace='cache'")

    async def fail_job(self, job: Job, error: str, p: Principal) -> None:
        job.status, job.error = "failed", error
        async with self.transaction(p) as conn:
            await conn.execute("SELECT id FROM rag.knowledge WHERE id=%s FOR UPDATE", (job.kb_id,))
            updated = await conn.execute(
                "UPDATE rag.jobs SET status='failed',error=%s,data=%s WHERE id=%s AND attempts=%s AND status='running'",
                (error, js(asdict(job)), job.id, job.attempts),
            )
            if updated.rowcount:
                await conn.execute(
                    "UPDATE rag.documents SET status='failed' WHERE id=%s AND version=%s",
                    (job.document_id, job.version),
                )

    async def get_job(self, job_id: str, p: Principal) -> Job:
        async with self.transaction(p) as conn:
            row = await (
                await conn.execute("SELECT data FROM rag.jobs WHERE id=%s", (job_id,))
            ).fetchone()
            if not row:
                raise PermissionError("Job unavailable")
            return Job(**row["data"])

    @staticmethod
    def ev(row: dict[str, Any]) -> Evidence:
        return Evidence(
            row["id"],
            row["document_id"],
            row["version"],
            row["text"],
            float(row.get("score", 1)),
            row["source_uri"],
            row["page"],
            row["section"],
            row["tenant_id"],
            row["acl_version"],
            row["title"],
        )

    async def dense(
        self, vector: list[float], kb_ids: tuple[str, ...], p: Principal, limit: int
    ) -> list[Evidence]:
        if not kb_ids:
            return []
        for kb_id in kb_ids:
            kb = await self.check_kb(kb_id, p)
            if kb["dimensions"] and kb["dimensions"] != len(vector):
                raise ValueError("Embedding model dimensions changed; reingest this knowledge base")
        async with self.transaction(p) as conn:
            rows = await (
                await conn.execute(
                    "SELECT c.*,d.title,d.source_uri,d.acl_version,1-(c.embedding <=> %s::vector) AS score FROM rag.chunks c JOIN rag.documents d ON d.id=c.document_id WHERE c.kb_id=ANY(%s) AND d.status='ready' AND c.version=d.version ORDER BY c.embedding <=> %s::vector,c.id LIMIT %s",
                    (json.dumps(vector), list(kb_ids), json.dumps(vector), limit),
                )
            ).fetchall()
            return [self.ev(r) for r in rows if r["score"] is not None and r["score"] > 0]

    async def keyword(
        self, text: str, kb_ids: tuple[str, ...], p: Principal, limit: int
    ) -> list[Evidence]:
        if not kb_ids:
            return []
        async with self.transaction(p) as conn:
            rows = await (
                await conn.execute(
                    "SELECT c.*,d.title,d.source_uri,d.acl_version,ts_rank(c.search_tsv,websearch_to_tsquery('english',%s)) AS score FROM rag.chunks c JOIN rag.documents d ON d.id=c.document_id WHERE c.kb_id=ANY(%s) AND d.status='ready' AND c.version=d.version AND c.search_tsv @@ websearch_to_tsquery('english',%s) ORDER BY score DESC,c.id LIMIT %s",
                    (text, list(kb_ids), text, limit),
                )
            ).fetchall()
            return [self.ev(r) for r in rows]

    async def evidence(self, ids: list[str], p: Principal) -> list[Evidence]:
        async with self.transaction(p) as conn:
            rows = await (
                await conn.execute(
                    "SELECT c.*,d.title,d.source_uri,d.acl_version FROM rag.chunks c JOIN rag.documents d ON d.id=c.document_id WHERE c.id=ANY(%s) AND d.status='ready' AND c.version=d.version",
                    (ids,),
                )
            ).fetchall()
            return [self.ev(r) for r in rows]

    async def document_chunks(
        self, doc_id: str, p: Principal, limit: int = 512
    ) -> tuple[list[Evidence], int]:
        if not 1 <= limit <= 512:
            raise ValueError("Invalid document read limit")
        await self.get_doc(doc_id, p)
        async with self.transaction(p) as conn:
            rows = await (
                await conn.execute(
                    "SELECT c.*,d.title,d.source_uri,d.acl_version,count(*) OVER() AS total_chunks "
                    "FROM rag.chunks c JOIN rag.documents d ON d.id=c.document_id "
                    "WHERE d.id=%s AND d.status='ready' AND c.version=d.version "
                    "ORDER BY COALESCE((c.data->>'ordinal')::int,0),c.id LIMIT %s",
                    (doc_id, limit),
                )
            ).fetchall()
            return [self.ev(r) for r in rows], int(rows[0]["total_chunks"]) if rows else 0

    async def revision(self, kb_ids: tuple[str, ...], p: Principal) -> str:
        kbs = [await self.check_kb(k, p) for k in kb_ids]
        docs = [asdict(d) for kb in kb_ids for d in await self.list_docs(p, kb)]
        return hashlib.sha256(
            json.dumps([kbs, docs], sort_keys=True, default=str).encode()
        ).hexdigest()

    async def create_session(self, data: dict[str, Any], p: Principal) -> dict[str, Any]:
        async with self.transaction(p) as conn:
            await conn.execute(
                "INSERT INTO rag.sessions(id,tenant_id,user_id,data) VALUES(%s,%s,%s,%s)",
                (
                    data["id"],
                    p.tenant_id,
                    p.user_id,
                    js({k: v for k, v in data.items() if k != "messages"}),
                ),
            )
        return data

    async def get_session(self, uid: str, p: Principal) -> dict[str, Any]:
        async with self.transaction(p) as conn:
            row = await (
                await conn.execute("SELECT data FROM rag.sessions WHERE id=%s", (uid,))
            ).fetchone()
            if not row:
                raise PermissionError("Session unavailable")
            messages = await (
                await conn.execute(
                    "SELECT data FROM rag.messages WHERE session_id=%s ORDER BY position", (uid,)
                )
            ).fetchall()
            return {**row["data"], "messages": normalize_messages([m["data"] for m in messages])}

    async def list_sessions(self, p: Principal) -> list[dict[str, Any]]:
        async with self.transaction(p) as conn:
            rows = await (
                await conn.execute(
                    "SELECT data FROM rag.sessions ORDER BY data->>'updated_at' DESC"
                )
            ).fetchall()
        return [{**r["data"], "messages": [], "summary": ""} for r in rows]

    async def context_session(self, uid: str, p: Principal) -> dict[str, Any]:
        async with self.transaction(p) as conn:
            row = await (
                await conn.execute("SELECT data FROM rag.sessions WHERE id=%s", (uid,))
            ).fetchone()
            if not row:
                raise PermissionError("Session unavailable")
            rows = await (
                await conn.execute(
                    "WITH answers AS (SELECT id,data FROM rag.messages WHERE session_id=%s "
                    "AND data->>'role'='assistant' AND data->>'status'='completed' "
                    "AND data->>'pending_run_id' IS NULL "
                    "AND COALESCE(data->>'answer_status','answered') IN ('answered','clarification') "
                    "ORDER BY position DESC LIMIT 8) "
                    "SELECT m.data FROM rag.messages m WHERE m.session_id=%s AND (m.id IN (SELECT id FROM answers) "
                    "OR m.id IN (SELECT COALESCE(a.data->>'parent_user_message_id', "
                    "(SELECT u.id FROM rag.messages u WHERE u.session_id=%s AND u.data->>'role'='user' "
                    "AND u.data->>'run_id'=a.data->>'run_id' ORDER BY u.position DESC LIMIT 1)) FROM answers a)) "
                    "ORDER BY m.position",
                    (uid, uid, uid),
                )
            ).fetchall()
            return {**row["data"], "messages": context_messages([m["data"] for m in rows])}

    async def save_session(self, data: dict[str, Any], p: Principal) -> None:
        async with self.transaction(p) as conn:
            await conn.execute(
                "UPDATE rag.sessions SET data=data || %s WHERE id=%s",
                (
                    js(
                        {
                            k: v
                            for k, v in data.items()
                            if k not in {"messages", "active_run_id", "updated_at"}
                        }
                    ),
                    data["id"],
                ),
            )

    async def delete_session(self, uid: str, p: Principal) -> None:
        await self.get_session(uid, p)
        async with self.transaction(p) as conn:
            for table in ("events", "receipts"):
                await conn.execute(
                    f"DELETE FROM rag.{table} WHERE run_id IN (SELECT id FROM rag.runs WHERE session_id=%s)",
                    (uid,),
                )
            await conn.execute("DELETE FROM rag.messages WHERE session_id=%s", (uid,))
            await conn.execute("DELETE FROM rag.runs WHERE session_id=%s", (uid,))
            await conn.execute("DELETE FROM rag.sessions WHERE id=%s", (uid,))
            await conn.execute(
                "DELETE FROM rag.user_state WHERE data->>'session_id'=%s OR namespace='cache'",
                (uid,),
            )

    async def begin_run(
        self, run: Run, message: dict[str, Any] | None, fingerprint: str, p: Principal
    ) -> tuple[Run, bool]:
        try:
            async with self.transaction(p) as conn:
                # Serializes idempotent retries even when they arrive on separate connections.
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (f"{p.tenant_id}:{p.user_id}:{run.client_message_id or run.id}",),
                )
                if run.client_message_id:
                    old = await (
                        await conn.execute(
                            "SELECT state,fingerprint FROM rag.runs WHERE client_message_id=%s",
                            (run.client_message_id,),
                        )
                    ).fetchone()
                    if old:
                        if old["fingerprint"] != fingerprint:
                            raise ConflictError(
                                "Message ID was already used for a different request"
                            )
                        return Run(**old["state"]), False
                if run.session_id:
                    session = await (
                        await conn.execute(
                            "SELECT data FROM rag.sessions WHERE id=%s FOR UPDATE",
                            (run.session_id,),
                        )
                    ).fetchone()
                    if not session:
                        raise PermissionError("Session unavailable")
                    active = await (
                        await conn.execute(
                            "SELECT id FROM rag.runs WHERE session_id=%s AND status IN ('pending','running')",
                            (run.session_id,),
                        )
                    ).fetchone()
                    if active:
                        raise ConflictError("This chat already has a running response")
                    data = session["data"]
                    rows = await (
                        await conn.execute(
                            "SELECT data FROM rag.messages WHERE session_id=%s ORDER BY position",
                            (run.session_id,),
                        )
                    ).fetchall()
                    working = {**data, "messages": [row["data"] for row in rows]}
                    prepare_answer(working, run, message)
                    data.update(active_run_id=run.id, updated_at=run.created_at)
                    if data["title"] == "New chat" and message:
                        data["title"] = str(message["content"])[:32]
                    await conn.execute(
                        "UPDATE rag.sessions SET data=%s WHERE id=%s", (js(data), run.session_id)
                    )
                    if message:
                        await self._message(conn, run.session_id, message, p)
                    answer = working["messages"][-1]
                    if run.regeneration_of_run_id:
                        await conn.execute(
                            "UPDATE rag.messages SET data=%s WHERE id=%s AND session_id=%s",
                            (js(answer), answer["id"], run.session_id),
                        )
                    else:
                        await self._message(conn, run.session_id, answer, p)
                run.answer = ""
                await conn.execute(
                    "INSERT INTO rag.runs(id,tenant_id,user_id,mode,status,state,session_id,client_message_id,fingerprint) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        run.id,
                        p.tenant_id,
                        p.user_id,
                        run.mode,
                        run.status,
                        js(asdict(run)),
                        run.session_id,
                        run.client_message_id,
                        fingerprint,
                    ),
                )
                return run, True
        except UniqueViolation as exc:
            raise ConflictError("This chat already has a running response") from exc

    async def get_run(self, uid: str, p: Principal) -> Run:
        async with self.transaction(p) as conn:
            row = await (
                await conn.execute("SELECT state FROM rag.runs WHERE id=%s", (uid,))
            ).fetchone()
            if not row:
                raise PermissionError("Run unavailable")
            return Run(**row["state"])

    async def save_run(self, run: Run, p: Principal) -> None:
        async with self.transaction(p) as conn:
            await conn.execute(
                "UPDATE rag.runs SET status=%s,mode=%s,state=%s WHERE id=%s AND status IN ('pending','running')",
                (run.status, run.mode, js(asdict(run)), run.id),
            )

    async def finish(self, run: Run, kind: str, data: dict[str, Any], p: Principal) -> bool:
        async with self.transaction(p) as conn:
            old = await (
                await conn.execute("SELECT status FROM rag.runs WHERE id=%s FOR UPDATE", (run.id,))
            ).fetchone()
            if not old or old["status"] in TERMINAL:
                return False
            await conn.execute(
                "UPDATE rag.runs SET status=%s,mode=%s,state=%s WHERE id=%s",
                (run.status, run.mode, js(asdict(run)), run.id),
            )
            await self._log(conn, run.id, kind, data, p)
            if run.session_id:
                finished = data.get("finished_at", datetime.now(UTC).isoformat())
                session = await (
                    await conn.execute(
                        "SELECT data FROM rag.sessions WHERE id=%s FOR UPDATE", (run.session_id,)
                    )
                ).fetchone()
                if not session:
                    return True
                rows = await (
                    await conn.execute(
                        "SELECT data FROM rag.messages WHERE session_id=%s ORDER BY position",
                        (run.session_id,),
                    )
                ).fetchall()
                working = {**session["data"], "messages": [row["data"] for row in rows]}
                answer = finish_answer(working, run, finished)
                await conn.execute(
                    "UPDATE rag.sessions SET data=data || %s WHERE id=%s",
                    (js({"active_run_id": None, "updated_at": finished}), run.session_id),
                )
                await conn.execute(
                    "INSERT INTO rag.messages(id,session_id,tenant_id,user_id,data) VALUES(%s,%s,%s,%s,%s) "
                    "ON CONFLICT(id) DO UPDATE SET data=EXCLUDED.data",
                    (answer["id"], run.session_id, p.tenant_id, p.user_id, js(answer)),
                )
            return True

    async def select_version(
        self, uid: str, message_id: str, run_id: str, expected: str, p: Principal
    ) -> dict[str, Any]:
        run = await self.get_run(run_id, p)
        async with self.transaction(p) as conn:
            row = await (
                await conn.execute("SELECT data FROM rag.sessions WHERE id=%s FOR UPDATE", (uid,))
            ).fetchone()
            if not row:
                raise PermissionError("Session unavailable")
            rows = await (
                await conn.execute(
                    "SELECT data FROM rag.messages WHERE session_id=%s ORDER BY position", (uid,)
                )
            ).fetchall()
            session = {**row["data"], "messages": [m["data"] for m in rows]}
            answer = choose_version(session, message_id, run, expected)
            await conn.execute(
                "UPDATE rag.messages SET data=%s WHERE id=%s AND session_id=%s",
                (js(answer), message_id, uid),
            )
            return answer

    async def _message(
        self,
        conn: AsyncConnection[dict[str, Any]],
        session_id: str,
        data: dict[str, Any],
        p: Principal,
    ) -> None:
        await conn.execute(
            "INSERT INTO rag.messages(id,session_id,tenant_id,user_id,data) VALUES(%s,%s,%s,%s,%s)",
            (data["id"], session_id, p.tenant_id, p.user_id, js(data)),
        )

    async def _log(
        self,
        conn: AsyncConnection[dict[str, Any]],
        run_id: str,
        kind: str,
        data: dict[str, Any],
        p: Principal,
    ) -> Event:
        await conn.execute("SELECT id FROM rag.runs WHERE id=%s FOR UPDATE", (run_id,))
        row = await (
            await conn.execute(
                "INSERT INTO rag.events(run_id,id,tenant_id,kind,payload) SELECT %s,COALESCE(max(id),0)+1,%s,%s,%s FROM rag.events WHERE run_id=%s RETURNING id,created_at::text",
                (run_id, p.tenant_id, kind, js(data), run_id),
            )
        ).fetchone()
        assert row is not None
        return Event(row["id"], run_id, kind, data, row["created_at"])

    async def log(self, run_id: str, kind: str, data: dict[str, Any], p: Principal) -> Event:
        async with self.transaction(p) as conn:
            row = await (
                await conn.execute("SELECT status FROM rag.runs WHERE id=%s FOR UPDATE", (run_id,))
            ).fetchone()
            if not row:
                raise PermissionError("Run unavailable")
            if row["status"] in TERMINAL:
                last = await (
                    await conn.execute(
                        "SELECT id,kind,payload,created_at::text FROM rag.events WHERE run_id=%s ORDER BY id DESC LIMIT 1",
                        (run_id,),
                    )
                ).fetchone()
                if not last:
                    raise ValueError("Terminal event missing")
                return Event(last["id"], run_id, last["kind"], last["payload"], last["created_at"])
            return await self._log(conn, run_id, kind, data, p)

    async def events(self, run_id: str, p: Principal, after: int = 0) -> list[Event]:
        await self.get_run(run_id, p)
        async with self.transaction(p) as conn:
            rows = await (
                await conn.execute(
                    "SELECT id,kind,payload,created_at::text FROM rag.events WHERE run_id=%s AND id>%s ORDER BY id",
                    (run_id, after),
                )
            ).fetchall()
            return [Event(r["id"], run_id, r["kind"], r["payload"], r["created_at"]) for r in rows]

    async def audit(self, data: dict[str, Any], p: Principal) -> None:
        async with self.transaction(p) as conn:
            await conn.execute(
                "INSERT INTO rag.audit(tenant_id,actor,operation,details) VALUES(%s,%s,%s,%s)",
                (p.tenant_id, p.user_id, data.get("action", "activity"), js(data)),
            )

    async def state_get(self, namespace: str, key: str, p: Principal) -> dict[str, Any] | None:
        async with self.transaction(p) as conn:
            row = await (
                await conn.execute(
                    "SELECT data FROM rag.user_state WHERE namespace=%s AND key=%s",
                    (namespace, key),
                )
            ).fetchone()
            return row["data"] if row else None

    async def state_put(
        self, namespace: str, key: str, value: dict[str, Any], p: Principal
    ) -> None:
        async with self.transaction(p) as conn:
            await conn.execute(
                "INSERT INTO rag.user_state(tenant_id,user_id,namespace,key,data) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(tenant_id,user_id,namespace,key) DO UPDATE SET data=EXCLUDED.data,updated_at=now()",
                (p.tenant_id, p.user_id, namespace, key, js(value)),
            )

    async def state_delete(self, namespace: str, key: str, p: Principal) -> None:
        async with self.transaction(p) as conn:
            await conn.execute(
                "DELETE FROM rag.user_state WHERE namespace=%s AND key=%s", (namespace, key)
            )

    async def state_list(self, namespace: str, p: Principal) -> list[dict[str, Any]]:
        async with self.transaction(p) as conn:
            return [
                r["data"]
                for r in await (
                    await conn.execute(
                        "SELECT data FROM rag.user_state WHERE namespace=%s", (namespace,)
                    )
                ).fetchall()
            ]

    async def ingest_metrics(self, p: Principal) -> dict[str, float | None]:
        async with self.transaction(p) as conn:
            row = await (
                await conn.execute(
                    "SELECT (SELECT count(*) FROM rag.documents WHERE status<>'deleted') AS documents,(SELECT count(*) FROM rag.chunks) AS chunks,(SELECT count(*) FROM rag.jobs WHERE status='done') AS done,(SELECT count(*) FROM rag.jobs) AS jobs"
                )
            ).fetchone()
            assert row is not None
            return {
                "document_count": float(row["documents"]),
                "chunk_count": float(row["chunks"]),
                "success_rate": row["done"] / row["jobs"] if row["jobs"] else 0.0,
            }
