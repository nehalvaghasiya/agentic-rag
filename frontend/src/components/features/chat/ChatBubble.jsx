import { Loader2 } from "lucide-react";
import { CitationChips } from "./CitationChips";
import { ResponseActions } from "./ResponseActions";

function richText(content, sources, onOpenSources) {
  return String(content).split("\n").map((line, index) => <p key={index} className={index ? "mt-3" : ""}>
    {line.split(/((?:\[\d+\][ \t]*)+|\*\*[^*]+\*\*)/g).map((part, i) => {
      if (/^\[\d+\]/.test(part)) return <CitationChips key={i} sources={sources} onOpenSources={onOpenSources}
        indices={[...part.matchAll(/\[(\d+)\]/g)].map(match => Number(match[1]) - 1)} />;
      return part.startsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : <span key={i}>{part}</span>;
    })}
  </p>);
}

export function ChatBubble({ role, content, sources = [], isStreaming, events = [], run, status, answerStatus,
  runId, versions = [], notice, lastAttemptRunId, versionBusy, isLatest, chatBusy, onRegenerate, onVersion, onOpen, onRetry, onReconnect }) {
  const user = role === "user";
  const failed = ["failed", "cancelled", "disconnected"].includes(status);
  const outcome = run?.answer_status || answerStatus || "answered";
  const needsAttention = outcome !== "answered" && outcome !== "clarification";
  const last = events.filter(event => !["token", "complete"].includes(event.type)).at(-1);
  const progress = ["retrieval_started", "retrieval", "agent_started", "tool_started"].includes(last?.type) ? "Reading documents…" :
    content || last?.type === "generation" ? "Writing response…" : "Preparing response…";
  const busy = isStreaming || versionBusy || chatBusy;
  return <article className={`flex min-w-0 ${user ? "justify-end" : "justify-start"}`} aria-label={user ? "Your message" : "Assistant response"}>
    <div className={user ? "max-w-[85%] rounded-2xl bg-accent px-4 py-3 text-sm leading-relaxed text-white" : "min-w-0 w-full py-1 text-base leading-[1.7] text-text"}>
      <div className="whitespace-pre-wrap break-words">{richText(content, sources, ids => onOpen?.("sources", ids))}</div>
      {!user && isStreaming && <div role="status" className="mt-2 flex items-center gap-2 text-sm text-muted"><Loader2 size={14} className="animate-spin motion-reduce:animate-none" />{progress}</div>}
      {!user && !isStreaming && needsAttention && <p className="mt-3 text-sm text-amber-700 dark:text-amber-300">{outcome === "citation_error"
        ? "The answer’s source references could not be verified."
        : outcome === "coverage_limit" ? "Some document content could not be covered."
        : "A supported document answer could not be completed."}</p>}
      {!user && notice && <p role="status" className="mt-3 text-sm text-muted">{notice}</p>}
      {!user && lastAttemptRunId && !isStreaming && <button type="button" className="min-h-11 text-sm text-accent underline"
        onClick={() => onOpen?.("activity", [], lastAttemptRunId)}>View attempt details</button>}
      {!user && (failed || needsAttention) && isLatest && !isStreaming && (onRegenerate || onRetry) && <button type="button" disabled={status === "disconnected" ? versionBusy : busy}
        onClick={status === "disconnected" ? onReconnect : onRegenerate || onRetry} className="mt-2 min-h-11 text-sm text-accent underline">{status === "disconnected" ? "Reconnect response" : "Retry response"}</button>}
      {!user && <ResponseActions content={content} sources={sources} versions={versions} runId={runId} busy={busy}
        canRegenerate={isLatest && !failed} onRegenerate={onRegenerate} onVersion={onVersion} onOpen={onOpen || (() => {})} />}
    </div>
  </article>;
}
