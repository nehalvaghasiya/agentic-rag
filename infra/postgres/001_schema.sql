-- Reference schema for production persistence. Application PgRepository wiring is not yet implemented.
-- Every service request must SET LOCAL app.tenant_id inside its transaction.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS rag;
CREATE TABLE IF NOT EXISTS rag.knowledge (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  name TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(tenant_id, name)
);
CREATE TABLE IF NOT EXISTS rag.documents (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  kb_id TEXT NOT NULL REFERENCES rag.knowledge(id),
  owner_id TEXT NOT NULL,
  groups TEXT[] NOT NULL DEFAULT '{}',
  title TEXT NOT NULL,
  source_uri TEXT NOT NULL,
  content_type TEXT NOT NULL,
  version INTEGER NOT NULL CHECK(version > 0),
  acl_version INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL CHECK(status IN ('queued','running','ready','failed','deleted')),
  modified_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS doc_tenant_kb ON rag.documents(tenant_id, kb_id);
CREATE TABLE IF NOT EXISTS rag.chunks (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  kb_id TEXT NOT NULL,
  document_id TEXT NOT NULL REFERENCES rag.documents(id),
  version INTEGER NOT NULL,
  page INTEGER,
  section TEXT,
  text TEXT NOT NULL,
  search_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
  embedding vector(1536),
  UNIQUE(document_id, version, id)
);
CREATE INDEX IF NOT EXISTS chunk_lexical ON rag.chunks USING gin(search_tsv);
CREATE INDEX IF NOT EXISTS chunk_filter ON rag.chunks(tenant_id, kb_id, document_id);
-- Build HNSW after bulk import; index dimension must match configured embedding model.
CREATE INDEX IF NOT EXISTS chunk_vector ON rag.chunks USING hnsw (embedding vector_cosine_ops);
CREATE TABLE IF NOT EXISTS rag.jobs (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  document_id TEXT NOT NULL REFERENCES rag.documents(id),
  status TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0,
  lease_until TIMESTAMPTZ,
  error TEXT,
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS jobs_claim ON rag.jobs(status, lease_until);
CREATE TABLE IF NOT EXISTS rag.runs (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  status TEXT NOT NULL,
  state JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS rag.events (
  run_id TEXT NOT NULL REFERENCES rag.runs(id),
  id BIGINT NOT NULL,
  tenant_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  payload JSONB NOT NULL,
  PRIMARY KEY(run_id, id)
);
CREATE TABLE IF NOT EXISTS rag.sessions (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  data JSONB NOT NULL DEFAULT '{}',
  expires_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS rag.memories (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  text TEXT NOT NULL,
  expires_at TIMESTAMPTZ,
  consent_version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS rag.receipts (
  run_id TEXT NOT NULL REFERENCES rag.runs(id),
  call_id TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  result JSONB NOT NULL,
  PRIMARY KEY(run_id, call_id)
);
CREATE TABLE IF NOT EXISTS rag.audit (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  actor TEXT NOT NULL,
  operation TEXT NOT NULL,
  details JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
DO $$
DECLARE tbl TEXT;
BEGIN
  FOREACH tbl IN ARRAY ARRAY['knowledge','documents','chunks','jobs','runs','events','sessions','memories','receipts','audit'] LOOP
    EXECUTE format('ALTER TABLE rag.%I ENABLE ROW LEVEL SECURITY', tbl);
    EXECUTE format('ALTER TABLE rag.%I FORCE ROW LEVEL SECURITY', tbl);
    EXECUTE format('DROP POLICY IF EXISTS tenant_policy ON rag.%I', tbl);
    EXECUTE format('CREATE POLICY tenant_policy ON rag.%I USING (tenant_id = current_setting(''app.tenant_id'', true)) WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true))', tbl);
  END LOOP;
END $$;
-- Application database role must NOT own tables and must NOT have BYPASSRLS.
