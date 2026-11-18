"""Explicit schema migration and least-privilege application-role provisioning."""

import sys
from pathlib import Path

from psycopg import AsyncConnection, sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from agentic_rag.core.config import Settings


async def migrate(settings: Settings) -> None:
    if not settings.database_url or not settings.database_admin_url:
        raise ValueError(
            "Set AGENTIC_RAG_DATABASE_URL and AGENTIC_RAG_DATABASE_ADMIN_URL for migration"
        )
    app = conninfo_to_dict(settings.database_url)
    admin = conninfo_to_dict(settings.database_admin_url)
    if any(app.get(k) != admin.get(k) for k in ("host", "port", "dbname")):
        raise ValueError("Admin and application database URLs must target the same database")
    role = str(app.get("user") or "")
    if not role or role == admin.get("user"):
        raise ValueError("Use a separate non-superuser application database role")
    root = Path(__file__).resolve().parents[3] / "infra" / "postgres"
    if not root.is_dir():
        candidates = [
            Path(__file__).resolve().parents[2] / "share" / "agentic-rag" / "migrations",
            Path(sys.prefix) / "share" / "agentic-rag" / "migrations",
        ]
        root = next((path for path in candidates if path.is_dir()), root)
    if not root.is_dir():
        raise ValueError("Packaged PostgreSQL migrations are unavailable")
    async with await AsyncConnection.connect(settings.database_admin_url) as conn:
        old = await (await conn.execute("SELECT to_regclass('rag.knowledge')")).fetchone()
        if old and old[0] is None:
            await conn.execute((root / "001_schema.sql").read_text(), prepare=False)
        exists = await (await conn.execute("SELECT to_regclass('rag.schema_version')")).fetchone()
        if exists and exists[0] is None:
            await conn.execute((root / "002_chat_runtime.sql").read_text(), prepare=False)
        version = await (
            await conn.execute("SELECT max(version) FROM rag.schema_version")
        ).fetchone()
        if version and version[0] < 3:
            await conn.execute((root / "003_document_deletion.sql").read_text(), prepare=False)
        role_row = await (
            await conn.execute(
                "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=%s", (role,)
            )
        ).fetchone()
        if not role_row:
            await conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(app.get("password", ""))
                )
            )
        elif role_row[0] or role_row[1]:
            raise ValueError("Existing application role must be NOSUPERUSER NOBYPASSRLS")
        await conn.execute("CREATE SCHEMA IF NOT EXISTS rag_checkpoints")
        await conn.execute(sql.SQL("GRANT USAGE ON SCHEMA rag TO {}").format(sql.Identifier(role)))
        await conn.execute(
            sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA rag TO {}").format(
                sql.Identifier(role)
            )
        )
        await conn.execute(
            sql.SQL("GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA rag TO {}").format(
                sql.Identifier(role)
            )
        )
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(
        make_conninfo(settings.database_admin_url, options="-c search_path=rag_checkpoints,public")
    ) as saver:
        await saver.setup()
    async with await AsyncConnection.connect(settings.database_admin_url) as conn:
        await conn.execute(
            sql.SQL("GRANT USAGE ON SCHEMA rag_checkpoints TO {}").format(sql.Identifier(role))
        )
        await conn.execute(
            sql.SQL(
                "GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA rag_checkpoints TO {}"
            ).format(sql.Identifier(role))
        )
    print("Database schema and application role ready.")
