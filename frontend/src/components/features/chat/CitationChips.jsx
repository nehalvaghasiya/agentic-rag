import { FileText, Wrench } from "lucide-react";

export function CitationChips({ sources, indices, onOpenSources }) {
  const groups = [];
  for (const index of indices) {
    const source = sources[index];
    if (!source) continue;
    const key = source.kind === "tool" ? `tool:${source.id}` : `${source.document_id || source.id}:${source.version}`;
    const existing = groups.find(group => group.key === key);
    if (existing) existing.ids.push(source.id);
    else groups.push({ key, source, ids: [source.id] });
  }
  return <span className="inline" data-citation-chips>
    {groups.slice(0, 2).map(group => <button key={group.key} type="button"
      onClick={() => onOpenSources?.(group.ids)} title={group.source.title}
      aria-label={`View source: ${group.source.title}${group.source.page != null ? `, page ${group.source.page}` : ""}`}
      className="citation-chip">
      {group.source.kind === "tool" ? <Wrench size={12} className="shrink-0" /> : <FileText size={12} className="shrink-0" />}
      <span className="max-w-36 truncate">{group.source.title}</span>
    </button>)}
    {groups.length > 2 && <button type="button" className="citation-chip" aria-label={`View ${groups.length - 2} more sources`}
      onClick={() => onOpenSources?.(groups.slice(2).flatMap(group => group.ids))}>+{groups.length - 2}</button>}
    {indices.filter(index => !sources[index]).map(index => <span key={index}>[{index + 1}]</span>)}
  </span>;
}
