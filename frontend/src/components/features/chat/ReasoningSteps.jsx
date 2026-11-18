import { useState } from "react";
import { ChevronDown, ChevronRight, Loader2, CheckCircle2 } from "lucide-react";

export function ReasoningSteps({ events = [], isStreaming, panel = false }) {
  const [expanded, setExpanded] = useState(false);
  const activity = events.filter(event => event.type !== "token" && event.type !== "complete");
  if (!activity.length) return panel ? <p className="text-sm text-muted">No execution activity is available.</p> : null;
  const last = activity.at(-1);
  return <div className="my-3 overflow-hidden rounded-lg border border-border">
    {!panel && <button type="button" onClick={() => setExpanded(value => !value)} aria-expanded={expanded}
      className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-muted">
      {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      {isStreaming ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
      <span>{isStreaming ? last.data.title || last.type : "Execution activity"}</span>
      <span className="ml-auto">{activity.length} events</span>
    </button>}
    {(expanded || panel) && <ol className={`space-y-4 ${panel ? "p-3" : "border-t border-border p-3"}`}>
      {activity.map(event => <li key={event.id} className={`text-xs ${event.data.parent_id ? "ml-4" : ""}`}>
        <div className="flex gap-2 font-medium text-text"><span>{event.data.title || event.type}</span>
          <time className="ml-auto font-normal text-muted" dateTime={event.timestamp}>{new Date(event.timestamp).toLocaleTimeString()}</time></div>
        {(event.type === "error" || event.type === "cancelled") && <p className="mt-1 text-red-500">{event.data.message}</p>}
        {event.data.description && <p className="mt-1 text-muted">{event.data.description}</p>}
        {event.type === "cache" && <p className="mt-1 text-muted">{event.data.layer}: {event.data.status}{event.data.origin_run_id ? ` · Original run ${event.data.origin_run_id}` : ""}</p>}
        {event.data.name && <p className="mt-1 text-muted">{event.data.name}{event.data.status ? ` · ${event.data.status}` : ""}
          {event.data.duration_ms != null ? ` · ${Math.round(event.data.duration_ms)} ms` : ""}</p>}
        {event.data.goals && Array.isArray(event.data.goals) && <ul className="mt-1 list-disc pl-4 text-muted">{event.data.goals.map((goal, i) => <li key={i}>{goal}</li>)}</ul>}
        {event.data.count != null && <p className="mt-1 text-muted">{event.data.count} passages · {event.data.strategy}</p>}
        {event.type === "context" && event.data.turns != null && <p className="mt-1 text-muted">{event.data.turns} recent turns · Summary {event.data.summary_used ? "used" : "not needed"}</p>}
        {(event.data.arguments || event.data.output) && <details className="mt-1 text-muted"><summary className="cursor-pointer">Tool details</summary>
          <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-words">{JSON.stringify(event.data.arguments || event.data.output, null, 2)}</pre></details>}
      </li>)}
    </ol>}
  </div>;
}
