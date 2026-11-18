import { useEffect, useState } from "react";
import { getActivity, getRun } from "../../../api/chat";
import { describeApiError } from "../../../api/client";
import { SidePanel } from "../../ui/SidePanel";
import { ReasoningSteps } from "./ReasoningSteps";
import { SourceList } from "./SourceList";

const titles = { sources: "Sources", details: "Response details", activity: "Activity", conversation: "Conversation details" };
const routes = { direct: "Direct LLM", rag: "Fast RAG", agentic: "Agentic RAG" };

function Details({ run }) {
  const coverage = run.coverage || { total_chunks: 0 };
  const rows = [
    ["Answer status", (run.answer_status || "answered").replaceAll("_", " ")],
    ["Routing", routes[run.execution_path]], ["Model", run.model || "Unavailable"],
    ["Response duration", `${((run.latency_ms || 0) / 1000).toFixed(1)} s`],
    ["Grounding", run.grounding === "model" ? "Model knowledge · No external sources used" : run.grounding],
    ["Response cache", run.served_from_cache ? "Cached response" : "Fresh response"],
    ["Cited passages", (run.sources || []).length], ["Retrieved passages", run.evidence_count],
    ...(coverage.total_chunks > 0 ? [["Document coverage", `${coverage.read_chunks}/${coverage.total_chunks} passages`],
      ["Reading strategy", { map_reduce: "Section summaries", full_document: "Whole document", lookup: "Selected passages", partial: "Partial document", none: "None" }[coverage.strategy]]] : []),
    ["Tool calls", run.tool_calls], ["Execution steps", run.steps],
    ...(run.route_reason ? [["Routing explanation", run.route_reason]] : []),
    ...Object.entries(run.usage || {}).map(([key, value]) => [key.replaceAll("_", " "), typeof value === "object" ? JSON.stringify(value) : String(value)]),
    ["Run ID", run.id], ...(run.regeneration_of_run_id ? [["Regenerated from", run.regeneration_of_run_id]] : []),
    ...(run.error ? [["Error reference", run.error]] : []),
  ];
  return <dl className="space-y-4">{rows.map(([label, value]) => <div key={label}>
    <dt className="mb-1 text-xs text-muted">{label}</dt><dd className="break-words text-sm leading-relaxed text-text">{value}</dd>
  </div>)}</dl>;
}

export function ResponsePanel({ panel, message, chat, docked, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const streaming = message?.isStreaming;
  const unavailable = (message?.sources || []).filter(source => source.available === false).map(source => source.id);
  const availabilityKey = unavailable.join(",");
  useEffect(() => {
    if (panel.section === "conversation") return;
    const controller = new AbortController();
    setData(null); setError("");
    if (!panel.runId) { setError("Details are unavailable because this response could not be started."); return; }
    const load = async () => {
      try {
        const [run, events] = await Promise.all([getRun(panel.runId, controller.signal),
          panel.section === "activity" ? getActivity(panel.runId, controller.signal) : Promise.resolve([])]);
        if (!controller.signal.aborted) setData({ run, events });
      } catch (failure) { if (!controller.signal.aborted) setError(describeApiError(failure)); }
    };
    void load();
    return () => controller.abort();
  }, [panel.runId, panel.section, attempt, streaming, availabilityKey]);
  const events = [...new Map([...(data?.events || []), ...(message && message.runId === panel.runId ? message.events : [])].map(event => [event.id, event])).values()].sort((a, b) => a.id - b.id);
  return <SidePanel title={titles[panel.section]} docked={docked} onClose={onClose}>
    {panel.section === "conversation" ? <dl className="space-y-4 text-sm text-text">
      <div><dt className="mb-1 text-xs text-muted">Routing</dt><dd>Automatic routing · Direct answers, fast retrieval, and deep research in one conversation</dd></div>
      <div><dt className="mb-1 text-xs text-muted">History summary</dt><dd>{chat.summaryStatus}</dd></div>
      <div><dt className="mb-1 text-xs text-muted">Conversation ID</dt><dd className="break-words">{chat.id}</dd></div>
    </dl> : error ? <div role="alert" className="text-sm text-text"><p>{error}</p>
      <button type="button" className="mt-2 min-h-11 text-accent underline" onClick={() => setAttempt(value => value + 1)}>Retry details</button></div> :
      !data ? <p role="status" className="text-sm text-muted">Loading {titles[panel.section].toLowerCase()}…</p> :
      panel.section === "sources" ? <SourceList sources={(data.run.sources || []).map(source => unavailable.includes(source.id)
        ? { ...source, available: false, title: "Source unavailable", excerpt: "" } : source)} selectedIds={panel.sourceIds} /> :
      panel.section === "details" ? <Details run={data.run} /> :
      <ReasoningSteps events={events} isStreaming={streaming} panel />}
  </SidePanel>;
}
