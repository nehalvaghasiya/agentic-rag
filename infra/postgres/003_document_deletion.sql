-- Permit an authorized UPDATE to produce a document tombstone. PostgreSQL also
-- applies SELECT policies to the updated row; hiding tombstones in this policy
-- prevents the status='deleted' transition itself. Tombstones contain metadata
-- only: API reads filter them and content/chunk policies require a live document.
DROP POLICY IF EXISTS tenant_policy ON rag.documents;
CREATE POLICY tenant_policy ON rag.documents USING (
 tenant_id=current_setting('app.tenant_id',true) AND
 (cardinality(groups)=0 OR owner_id=current_setting('app.user_id',true)
 OR COALESCE(NULLIF(current_setting('app.roles',true),''),'[]')::jsonb ? 'admin'
 OR groups && ARRAY(SELECT jsonb_array_elements_text(COALESCE(NULLIF(current_setting('app.groups',true),''),'[]')::jsonb)))
) WITH CHECK (tenant_id=current_setting('app.tenant_id',true));
DROP POLICY IF EXISTS tenant_policy ON rag.chunks;
CREATE POLICY tenant_policy ON rag.chunks USING (
 tenant_id=current_setting('app.tenant_id',true) AND EXISTS(
  SELECT 1 FROM rag.documents d JOIN rag.knowledge k ON k.id=d.kb_id
  WHERE d.id=document_id AND d.status<>'deleted' AND NOT k.deleted)
) WITH CHECK (tenant_id=current_setting('app.tenant_id',true));
DROP POLICY IF EXISTS tenant_policy ON rag.contents;
CREATE POLICY tenant_policy ON rag.contents USING (
 tenant_id=current_setting('app.tenant_id',true) AND EXISTS(
  SELECT 1 FROM rag.documents d JOIN rag.knowledge k ON k.id=d.kb_id
  WHERE d.id=document_id AND d.status<>'deleted' AND NOT k.deleted)
) WITH CHECK (tenant_id=current_setting('app.tenant_id',true));
INSERT INTO rag.schema_version VALUES(3) ON CONFLICT DO NOTHING;
