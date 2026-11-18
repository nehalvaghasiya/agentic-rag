-- Additive chat runtime migration; original data is preserved.
CREATE TABLE IF NOT EXISTS rag.schema_version (version INTEGER PRIMARY KEY);
ALTER TABLE rag.knowledge ADD COLUMN IF NOT EXISTS revision BIGINT NOT NULL DEFAULT 1;
ALTER TABLE rag.knowledge ADD COLUMN IF NOT EXISTS embedding_model TEXT;
ALTER TABLE rag.knowledge ADD COLUMN IF NOT EXISTS dimensions INTEGER;
ALTER TABLE rag.knowledge ADD COLUMN IF NOT EXISTS deleted BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE rag.documents ADD COLUMN IF NOT EXISTS data JSONB NOT NULL DEFAULT '{}';
ALTER TABLE rag.documents DROP CONSTRAINT IF EXISTS documents_status_check;
ALTER TABLE rag.documents ADD CONSTRAINT documents_status_check
 CHECK(status IN ('processing','queued','running','ready','failed','deleted'));
DROP INDEX IF EXISTS rag.chunk_vector;
ALTER TABLE rag.chunks ALTER COLUMN embedding TYPE vector;
ALTER TABLE rag.chunks ADD COLUMN IF NOT EXISTS data JSONB NOT NULL DEFAULT '{}';
ALTER TABLE rag.jobs ADD COLUMN IF NOT EXISTS data JSONB NOT NULL DEFAULT '{}';
ALTER TABLE rag.runs ADD COLUMN IF NOT EXISTS session_id TEXT REFERENCES rag.sessions(id);
ALTER TABLE rag.runs ADD COLUMN IF NOT EXISTS client_message_id TEXT;
ALTER TABLE rag.runs ADD COLUMN IF NOT EXISTS fingerprint TEXT NOT NULL DEFAULT '';
CREATE UNIQUE INDEX IF NOT EXISTS run_idempotency ON rag.runs(tenant_id,user_id,client_message_id)
 WHERE client_message_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS one_active_chat_turn ON rag.runs(session_id)
 WHERE session_id IS NOT NULL AND status IN ('pending','running');
ALTER TABLE rag.events ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();
CREATE TABLE IF NOT EXISTS rag.contents (
 document_id TEXT PRIMARY KEY REFERENCES rag.documents(id), tenant_id TEXT NOT NULL,
 version INTEGER NOT NULL, content BYTEA NOT NULL
);
CREATE TABLE IF NOT EXISTS rag.messages (
 id TEXT PRIMARY KEY, session_id TEXT NOT NULL REFERENCES rag.sessions(id),
 tenant_id TEXT NOT NULL, user_id TEXT NOT NULL, position BIGINT GENERATED ALWAYS AS IDENTITY,
 data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_order ON rag.messages(session_id,position);
CREATE TABLE IF NOT EXISTS rag.user_state (
 tenant_id TEXT NOT NULL, user_id TEXT NOT NULL, namespace TEXT NOT NULL, key TEXT NOT NULL,
 data JSONB NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,user_id,namespace,key)
);
CREATE INDEX IF NOT EXISTS user_state_namespace ON rag.user_state(tenant_id,user_id,namespace);
DO $$
DECLARE tbl TEXT;
BEGIN
 FOREACH tbl IN ARRAY ARRAY['contents','messages','user_state'] LOOP
  EXECUTE format('ALTER TABLE rag.%I ENABLE ROW LEVEL SECURITY',tbl);
  EXECUTE format('ALTER TABLE rag.%I FORCE ROW LEVEL SECURITY',tbl);
  EXECUTE format('DROP POLICY IF EXISTS tenant_policy ON rag.%I',tbl);
  EXECUTE format('CREATE POLICY tenant_policy ON rag.%I USING (tenant_id=current_setting(''app.tenant_id'',true)) WITH CHECK (tenant_id=current_setting(''app.tenant_id'',true))',tbl);
 END LOOP;
 FOREACH tbl IN ARRAY ARRAY['sessions','runs','messages','user_state'] LOOP
  EXECUTE format('DROP POLICY IF EXISTS tenant_policy ON rag.%I',tbl);
  EXECUTE format('CREATE POLICY tenant_policy ON rag.%I USING (tenant_id=current_setting(''app.tenant_id'',true) AND user_id=current_setting(''app.user_id'',true)) WITH CHECK (tenant_id=current_setting(''app.tenant_id'',true) AND user_id=current_setting(''app.user_id'',true))',tbl);
 END LOOP;
END $$;
DROP POLICY IF EXISTS tenant_policy ON rag.documents;
CREATE POLICY tenant_policy ON rag.documents USING (
 tenant_id=current_setting('app.tenant_id',true) AND status<>'deleted' AND
 (cardinality(groups)=0 OR owner_id=current_setting('app.user_id',true)
 OR COALESCE(NULLIF(current_setting('app.roles',true),''),'[]')::jsonb ? 'admin'
 OR groups && ARRAY(SELECT jsonb_array_elements_text(COALESCE(NULLIF(current_setting('app.groups',true),''),'[]')::jsonb)))
) WITH CHECK (tenant_id=current_setting('app.tenant_id',true));
DROP POLICY IF EXISTS tenant_policy ON rag.chunks;
CREATE POLICY tenant_policy ON rag.chunks USING (
 tenant_id=current_setting('app.tenant_id',true) AND EXISTS(SELECT 1 FROM rag.documents d WHERE d.id=document_id)
) WITH CHECK (tenant_id=current_setting('app.tenant_id',true));
DROP POLICY IF EXISTS tenant_policy ON rag.contents;
CREATE POLICY tenant_policy ON rag.contents USING (
 tenant_id=current_setting('app.tenant_id',true) AND EXISTS(SELECT 1 FROM rag.documents d WHERE d.id=document_id)
) WITH CHECK (tenant_id=current_setting('app.tenant_id',true));
DROP POLICY IF EXISTS tenant_policy ON rag.events;
CREATE POLICY tenant_policy ON rag.events USING (
 tenant_id=current_setting('app.tenant_id',true) AND EXISTS(SELECT 1 FROM rag.runs r WHERE r.id=run_id)
) WITH CHECK (tenant_id=current_setting('app.tenant_id',true) AND EXISTS(SELECT 1 FROM rag.runs r WHERE r.id=run_id));
INSERT INTO rag.schema_version VALUES(2) ON CONFLICT DO NOTHING;
