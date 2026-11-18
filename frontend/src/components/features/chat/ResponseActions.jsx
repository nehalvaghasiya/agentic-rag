import { useEffect, useRef, useState } from "react";
import { Check, ChevronLeft, ChevronRight, ClipboardCopy, Copy, FileSearch, Info, ListOrdered, RotateCcw } from "lucide-react";
import { ActionMenu } from "../../ui/ActionMenu";

export function ResponseActions({ content, sources = [], versions = [], runId, busy, canRegenerate, onRegenerate, onVersion, onOpen }) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  const copy = async withCitations => {
    try {
      const bibliography = withCitations ? "\n\nSources\n" + sources.map((source, index) =>
        `[${index + 1}] ${source.title}${source.page != null ? ` · Page ${source.page}` : ""}${source.version != null ? ` · Version ${source.version}` : ""}${source.available === false ? " · Unavailable" : ""}`).join("\n") : "";
      await navigator.clipboard.writeText(content + bibliography);
      setCopyError(""); setCopied(true); clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 2000);
    } catch { setCopyError("Couldn’t copy. Select the answer text to copy it."); }
  };
  const completed = versions.filter(version => version.status === "completed");
  const at = completed.findIndex(version => version.run_id === runId);
  const items = [
    ...(sources.length ? [{ label: "View sources", icon: FileSearch, onSelect: () => onOpen("sources") }] : []),
    { label: "Response details", icon: Info, onSelect: () => onOpen("details") },
    { label: "View activity", icon: ListOrdered, onSelect: () => onOpen("activity") },
    ...(sources.length ? [{ label: "Copy with citations", icon: ClipboardCopy, onSelect: () => void copy(true) }] : []),
  ];
  return <div className="mt-3">
    <div className="flex flex-wrap items-center gap-0.5 text-muted" role="group" aria-label="Response actions">
      <button type="button" className="response-icon" aria-label={copied ? "Copied" : "Copy response"} title={copied ? "Copied" : "Copy response"}
        disabled={busy || !content} onClick={() => void copy(false)}>{copied ? <Check size={17} /> : <Copy size={17} />}</button>
      {canRegenerate && <button type="button" className="response-icon" aria-label="Regenerate response" title="Regenerate response"
        disabled={busy} onClick={onRegenerate}><RotateCcw size={17} /></button>}
      <ActionMenu label="More response options" items={items} />
      {completed.length > 1 && at >= 0 && <div className="ml-2 flex items-center text-xs" role="group" aria-label="Answer versions">
        <button type="button" className="response-icon" disabled={busy || at === 0} aria-label="Previous answer version" title="Previous answer version"
          onClick={() => onVersion(completed[at - 1].run_id)}><ChevronLeft size={15} /></button>
        <span className="min-w-10 text-center tabular-nums" aria-live="polite">{at + 1} / {completed.length}</span>
        <button type="button" className="response-icon" disabled={busy || at === completed.length - 1} aria-label="Next answer version" title="Next answer version"
          onClick={() => onVersion(completed[at + 1].run_id)}><ChevronRight size={15} /></button>
      </div>}
    </div>
    {copied && <span role="status" className="sr-only">Response copied</span>}
    {copyError && <p role="status" className="mt-1 text-xs text-muted">{copyError}</p>}
  </div>;
}
