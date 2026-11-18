import { useState } from "react";
import { describeApiError } from "../../../api/client";
import { Input } from "../../ui/Input";
import { Modal } from "../../ui/Modal";
import { Button } from "../../ui/Button";
import { DocumentPicker } from "./DocumentPicker";

export function CreateKnowledgeBaseModal({ open, onClose, onCreate, onOpenCreated }) {
  const [name, setName] = useState("");
  const [files, setFiles] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [createdId, setCreatedId] = useState(null);
  function close() { if (submitting) return; setName(""); setFiles([]); setError(""); setCreatedId(null); onClose(); }
  return <Modal open={open} title="Create Knowledge Base" busy={submitting} onClose={close} footer={<div className="flex justify-end gap-2">
    <Button disabled={submitting} onClick={close}>Cancel</Button>
    {createdId && error ? <Button variant="primary" onClick={() => { onOpenCreated?.(createdId); close(); }}>Open knowledge base</Button> :
      <Button variant="primary" disabled={submitting || !name.trim() || !files.length} onClick={async () => {
        setSubmitting(true); setError("");
        try { await onCreate({ name: name.trim(), files, onCreated: setCreatedId }); setName(""); setFiles([]); setCreatedId(null); }
        catch (failure) { setError(describeApiError(failure)); }
        finally { setSubmitting(false); }
      }}>{submitting ? "Creating…" : "Create"}</Button>}
  </div>}>
    <div className="space-y-4">
      {error && <div role="alert" className="whitespace-pre-line rounded border border-red-400/40 p-3 text-sm text-text">{error}</div>}
      {createdId && error && <p className="text-sm text-text">Your knowledge base was created. Open it to check which documents were accepted before uploading again.</p>}
      <label className="block text-xs text-muted">Name<Input maxLength={100} disabled={submitting || Boolean(createdId)} value={name} onChange={event => { setName(event.target.value); setError(""); }} placeholder="e.g., Nvidia Q2 results" /></label>
      <DocumentPicker files={files} disabled={submitting || Boolean(createdId)} onError={setError} onChange={next => {
        setFiles(next); if (!name.trim() && next[0]) setName(next[0].name.replace(/\.[^.]+$/, ""));
      }} />
      <p className="text-xs text-muted">Documents use the server’s configured embedding model. Processing status appears on the dashboard after upload.</p>
    </div>
  </Modal>;
}
