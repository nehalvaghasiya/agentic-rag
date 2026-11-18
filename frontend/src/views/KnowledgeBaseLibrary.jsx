import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Database, Plus, Trash2 } from "lucide-react";
import { describeApiError } from "../api/client";
import { ConfirmDeleteModal } from "../components/features/knowledge-base/ConfirmDeleteModal";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { useAppState } from "../state/AppStateContext";
import { formatBytes, formatIsoDate } from "../utils/format";

export function KnowledgeBaseLibrary({ onCreate }) {
  const { knowledgeBases, knowledgeLoading, knowledgeFailure, actions } = useAppState();
  const [query, setQuery] = useState("");
  const [target, setTarget] = useState(null);
  const location = useLocation();
  const [notice, setNotice] = useState(location.state?.notice || "");
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(null);
  const navigate = useNavigate();
  useEffect(() => { void actions.refreshKnowledge().catch(() => {}); }, [actions]);
  const visible = useMemo(() => [...knowledgeBases].filter(kb => kb.name.toLowerCase().includes(query.trim().toLowerCase()))
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt) || a.name.localeCompare(b.name)), [knowledgeBases, query]);
  return <div className="h-full overflow-auto">
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border py-5 pl-16 pr-6 lg:pl-6">
      <div><h1 className="text-xl font-semibold text-text">Knowledge Bases</h1><p className="mt-1 text-sm text-muted">View and manage your documents and knowledge bases.</p></div>
      <Button variant="primary" onClick={onCreate}><Plus size={16} />Create Knowledge Base</Button>
    </header>
    <div className="space-y-5 px-6 py-6">
      <p role="status" className="text-sm text-text">{notice}</p>
      {(knowledgeFailure || error) && <div role="alert" className="rounded border border-red-400/40 p-3 text-sm text-text">
        <p className="whitespace-pre-line">{knowledgeFailure || error}</p><Button className="mt-2" onClick={() => { setError(""); void actions.refreshKnowledge().catch(() => {}); }}>Retry</Button>
      </div>}
      <label className="block max-w-md text-xs text-muted">Search knowledge bases<Input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search by name…" /></label>
      {knowledgeLoading && !knowledgeBases.length && <p className="py-10 text-center text-sm text-muted">Loading knowledge bases…</p>}
      {!knowledgeLoading && !knowledgeFailure && !knowledgeBases.length && <div className="rounded-lg border border-dashed border-border py-14 text-center">
        <Database className="mx-auto mb-4 text-muted" size={32} /><h2 className="font-semibold text-text">No knowledge bases yet</h2>
        <p className="mt-2 text-sm text-muted">Create a knowledge base to upload and organize your documents.</p><Button className="mt-4" onClick={onCreate}>Create your first knowledge base</Button>
      </div>}
      {knowledgeBases.length > 0 && !visible.length && <p className="py-10 text-center text-sm text-muted">No knowledge bases match your search.</p>}
      <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">{visible.map(kb => {
        const processing = kb.documents.filter(doc => ["processing", "queued", "running"].includes(doc.status)).length;
        const failed = kb.documents.filter(doc => doc.status === "failed").length;
        return <article key={kb.id} className="flex flex-col rounded-lg border border-border bg-surface p-5">
          <Link to={`/kb/${kb.id}`} className="break-words text-lg font-semibold text-text hover:underline">{kb.name}</Link>
          <p className="mt-2 text-sm text-muted">{kb.documents.length} document{kb.documents.length === 1 ? "" : "s"} · {formatBytes(kb.documents.reduce((sum, doc) => sum + doc.size, 0))}</p>
          <p className="mt-1 text-xs text-muted">{processing ? `${processing} processing` : kb.documents.length ? "Processing complete" : "Empty knowledge base"}{failed ? ` · ${failed} failed` : ""}</p>
          <p className="mt-2 text-xs text-muted">Created {formatIsoDate(kb.createdAt)}</p>
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <Link to={`/kb/${kb.id}`} className="rounded border border-border px-3 py-2 text-sm text-text hover:bg-border/30" aria-label={`Open ${kb.name}`}>Open</Link>
            <Button size="sm" disabled={Boolean(starting)} onClick={async () => {
              setStarting(kb.id); setError("");
              try { const chat = await actions.createChat({ kbId: kb.id }); navigate(`/chat/${chat.id}`); }
              catch (failure) { setError(describeApiError(failure)); } finally { setStarting(null); }
            }}>{starting === kb.id ? "Opening…" : "Chat with this knowledge base"}</Button>
            <Button size="sm" disabled={!kb.canDelete} title={kb.canDelete ? `Delete ${kb.name}` : "An admin role is required to delete a knowledge base."}
              aria-label={`Delete knowledge base ${kb.name}`} onClick={() => setTarget({ kind: "knowledge", id: kb.id, name: kb.name, count: kb.documents.length })}><Trash2 size={14} />Delete</Button>
          </div>
          {!kb.canDelete && <p className="mt-2 text-xs text-muted">An admin role is required to delete this knowledge base.</p>}
        </article>;
      })}</div>
    </div>
    {target && <ConfirmDeleteModal key={target.id} target={target} onClose={() => setTarget(null)} onConfirm={async () => {
      await actions.deleteKnowledgeBase(target.id); setNotice(`Deleted knowledge base ${target.name}.`);
    }} />}
  </div>;
}
