import { X } from "lucide-react";
import { formatBytes } from "../../../utils/format";

export function FileList({ files, onRemove, disabled = false }) {
  return files.length ? <ul className="mt-3 space-y-2" aria-label="Selected files">{files.map((file, index) =>
    <li key={`${file.name}-${index}`} className="flex items-center gap-3 rounded border border-border px-3 py-2 text-sm text-text">
      <span className="min-w-0 flex-1 truncate">{file.name}</span><span className="shrink-0 text-xs text-muted">{formatBytes(file.size)}</span>
      <button type="button" disabled={disabled} aria-label={`Remove ${file.name}`} onClick={() => onRemove(index)} className="rounded p-1 hover:bg-border/30 disabled:opacity-50"><X size={16} /></button>
    </li>)}</ul> : null;
}
