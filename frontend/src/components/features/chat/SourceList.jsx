import { useEffect, useRef, useState } from "react";
import { FileText, Wrench } from "lucide-react";
import { DocumentPreview } from "../knowledge-base/DocumentPreview";

export function SourceList({ sources = [], selectedIds = [] }) {
  const [expanded, setExpanded] = useState([]);
  const [preview, setPreview] = useState(null);
  const selected = useRef(null);
  const selectedKey = selectedIds.join(",");
  useEffect(() => { selected.current?.scrollIntoView({ block: "nearest", behavior: "instant" }); }, [selectedKey]);
  const groups = [];
  sources.forEach((source, index) => {
    const key = source.kind === "tool" ? `tool:${source.id}` : `${source.document_id || source.id}:${source.version}`;
    const existing = groups.find(group => group.key === key);
    const item = { ...source, number: index + 1 };
    if (existing) existing.items.push(item);
    else groups.push({ key, source, items: [item] });
  });
  if (!sources.length) return <p className="text-sm text-muted">This answer has no cited sources.</p>;
  return <section aria-label="Answer sources">
    <p className="mb-5 text-xs text-muted">{groups.length} {groups.length === 1 ? "source" : "sources"} · {sources.length} cited {sources.length === 1 ? "passage" : "passages"}</p>
    <ol className="space-y-6">{groups.map(group => <li key={group.key} className="border-b border-border pb-6 last:border-0">
      <div className="mb-3 flex items-start gap-2 font-medium text-text">
        {group.source.kind === "tool" ? <Wrench size={16} className="mt-0.5 shrink-0 text-muted" /> : <FileText size={16} className="mt-0.5 shrink-0 text-muted" />}
        <h3 className="min-w-0 break-words text-sm">{group.source.title}</h3>
      </div>
      <ol className="space-y-3">{group.items.map(source => {
        const active = selectedIds.includes(source.id);
        const full = active || expanded.includes(source.id);
        return <li key={source.id} ref={active && source.id === selectedIds[0] ? selected : undefined}
          className={`scroll-mt-3 rounded-lg p-3 ${active ? "bg-accent/10 ring-1 ring-accent/30" : "bg-bg"}`}>
          <p className="mb-2 text-xs text-muted">[{source.number}]
            {source.page != null ? ` · Page ${source.page}` : ""}{source.section ? ` · ${source.section}` : ""}
            {source.version != null ? ` · Version ${source.version}` : ""}{source.kind === "tool" ? " · Tool result" : ""}</p>
          {source.available === false ? <p className="text-sm text-muted">This source is no longer available.</p> : <>
            <p className={`whitespace-pre-wrap break-words text-sm leading-relaxed text-text ${full ? "" : "line-clamp-3"}`}>{source.excerpt || "No excerpt provided."}</p>
            {!active && source.excerpt && <button type="button" className="min-h-11 text-xs text-accent hover:underline" aria-expanded={full}
              onClick={() => setExpanded(previous => full ? previous.filter(id => id !== source.id) : [...previous, source.id])}>{full ? "Show less" : "Show more"}</button>}
          </>}
          {source.observed_at && <p className="mt-2 text-xs text-muted">Observed {new Date(source.observed_at).toLocaleString()}</p>}
        </li>;
      })}</ol>
      {group.source.kind !== "tool" && group.source.document_id && group.source.version != null && group.items.some(source => source.available !== false) &&
        <button type="button" className="mt-1 min-h-11 text-xs font-medium text-accent hover:underline"
          onClick={() => setPreview({ id: group.source.document_id, name: group.source.title, version: group.source.version })}>Open document</button>}
    </li>)}</ol>
    {preview && <DocumentPreview document={preview} onClose={() => setPreview(null)} />}
  </section>;
}
