import { Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { describeApiError } from "../api/client";
import { ApiError } from "../api/client";
import { StatGrid } from "../components/features/knowledge-base/StatGrid";
import { ConfirmDeleteModal } from "../components/features/knowledge-base/ConfirmDeleteModal";
import { DocumentPreview, DownloadDocumentButton } from "../components/features/knowledge-base/DocumentPreview";
import { UploadDocuments } from "../components/features/knowledge-base/UploadDocuments";
import { Button } from "../components/ui/Button";
import { useAppState } from "../state/AppStateContext";
import { formatBytes, formatIsoDate } from "../utils/format";

export function KnowledgeBaseDashboard() {
  const { kbId } = useParams();
  const navigate = useNavigate();
  const { knowledgeBases, knowledgeFailure, actions } = useAppState();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [target, setTarget] = useState(null);
  const [previewId, setPreviewId] = useState(null);
  const [notice, setNotice] = useState("");
  const [attempt, setAttempt] = useState(0);
  const kb = knowledgeBases.find(k => k.id === kbId);
  const stats = useMemo(() => kb ? actions.computeKbStats(kb) : null, [kb, actions]);
  const announce = useCallback(message => setNotice(message), []);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(""); setPreviewId(null);
    actions.refreshKnowledgeBase(kbId, controller.signal).catch(failure => {
      if (!controller.signal.aborted) setError(failure instanceof ApiError && failure.httpStatus === 403
        ? "This knowledge base is unavailable or you no longer have access to it." : describeApiError(failure));
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [kbId, actions, attempt]);
  const preview = kb?.documents.find(doc => doc.id === previewId);
  return <div className="flex h-full flex-col overflow-hidden">
    <header className="border-b border-border py-5 pl-16 pr-6 lg:pl-6">
      <Link to="/kb" className="text-sm text-accent hover:underline">← Back to Knowledge Bases</Link>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-text">{kb?.name || "Knowledge Base"}</h1>
        {kb && <div className="flex flex-wrap items-center gap-2"><Button onClick={() => { setAttempt(value => value + 1); void actions.refreshKnowledge().catch(() => {}); }}>Refresh</Button>
          <Button disabled={!kb.canDelete} title={kb.canDelete ? "Delete knowledge base" : "An admin role is required to delete a knowledge base."} onClick={() => setTarget({ kind: "knowledge", id: kb.id, name: kb.name, count: kb.documents.length })}><Trash2 size={16} />Delete knowledge base</Button></div>}
      </div>
      {kb && !kb.canDelete && <p className="mt-2 text-xs text-muted">An admin role is required to delete this knowledge base.</p>}
    </header>
    <div className="flex-1 space-y-6 overflow-auto px-6 py-6">
      <p role="status" className="text-sm text-text">{notice}</p>
      {(error || knowledgeFailure) && <div role="alert" className="rounded border border-red-400/40 p-3 text-sm text-text"><p className="whitespace-pre-line">{error || knowledgeFailure}</p><Button className="mt-2" onClick={() => { setAttempt(value => value + 1); void actions.refreshKnowledge().catch(() => {}); }}>Retry</Button></div>}
      {loading && !kb && <p className="text-sm text-muted">Loading knowledge base…</p>}
      {!loading && !kb && !error && <p className="text-sm text-muted">This knowledge base is unavailable or you no longer have access to it.</p>}
      {kb && stats && <><StatGrid stats={stats} /><UploadDocuments key={kb.id} kbId={kb.id} onUploaded={announce} />
        <section aria-label="Documents"><h2 className="mb-3 text-sm font-semibold text-text">Documents ({kb.documents.length})</h2>
          {!kb.documents.length ? <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted">No documents yet. Add documents above to start building this knowledge base.</div> :
            <ul className="divide-y divide-border rounded-lg border border-border bg-surface">{kb.documents.map(doc => {
              const processing = ["processing", "queued", "running"].includes(doc.status);
              const status = processing ? "Processing" : doc.status === "failed" ? "Failed" : doc.status;
              return <li key={doc.id} className="flex flex-wrap items-center justify-between gap-4 p-4">
                <div className="min-w-0 flex-1"><button className="break-all text-left text-sm font-medium text-text hover:underline" onClick={() => setPreviewId(doc.id)}>{doc.name}</button>
                  <p className="mt-1 text-xs text-muted">{formatBytes(doc.size)} · {doc.type} · Uploaded {formatIsoDate(doc.uploadedAt)}</p>
                  {!doc.canDelete && <p className="mt-1 text-xs text-muted">Only the owner or an admin can delete this document.</p>}
                  {status === "Failed" && <p className="mt-1 text-xs text-red-600 dark:text-red-300">Indexing failed. You can preview or download the original, or delete and upload it again.</p>}
                </div>
                <span className={`rounded-full border px-2 py-1 text-xs ${status === "Failed" ? "border-red-500/40 text-red-600 dark:text-red-300" : processing ? "border-amber-500/40 text-amber-700 dark:text-amber-300" : "border-emerald-500/40 text-emerald-700 dark:text-emerald-300"}`}>{status}</span>
                <div className="flex flex-wrap items-start gap-2"><Button size="sm" aria-label={`Preview ${doc.name}`} onClick={() => setPreviewId(doc.id)}>Preview</Button>
                  <DownloadDocumentButton document={doc} />
                  <Button size="sm" disabled={!doc.canDelete} aria-label={`Delete document ${doc.name}`} onClick={() => setTarget({ kind: "document", id: doc.id, name: doc.name })}><Trash2 size={14} />Delete</Button></div>
              </li>;
            })}</ul>}
        </section></>}
    </div>
    {preview && <DocumentPreview key={`${preview.id}-${preview.version}`} document={preview} onClose={() => setPreviewId(null)} />}
    {target && <ConfirmDeleteModal key={target.id} target={target} onClose={() => setTarget(null)} onConfirm={async () => {
      if (target.kind === "knowledge") { await actions.deleteKnowledgeBase(target.id); navigate("/kb", { state: { notice: `Deleted knowledge base ${target.name}.` } }); }
      else { await actions.deleteDocument(kbId, target.id); setNotice(`Deleted document ${target.name}.`); }
    }} />}
  </div>;
}
