import { Loader2 } from "lucide-react";
import { ReasoningSteps } from "./ReasoningSteps";
import { SourceList } from "./SourceList";

function renderRichText(content) {
  const lines = String(content).split("\n");

  return lines.map((line, idx) => {
    const parts = [];
    let rest = line;

    while (rest.includes("**")) {
      const start = rest.indexOf("**");
      const end = rest.indexOf("**", start + 2);
      if (end === -1) break;

      const before = rest.slice(0, start);
      const bold = rest.slice(start + 2, end);
      const after = rest.slice(end + 2);

      if (before) parts.push({ type: "text", value: before });
      if (bold) parts.push({ type: "bold", value: bold });

      rest = after;
    }

    if (rest) parts.push({ type: "text", value: rest });

    return (
      <p key={idx} className={idx === 0 ? "" : "mt-2"}>
        {parts.map((p, pIdx) =>
          p.type === "bold" ? (
            <strong key={pIdx} className="text-text">
              {p.value}
            </strong>
          ) : (
            <span key={pIdx}>{p.value}</span>
          )
        )}
      </p>
    );
  });
}

export function ChatBubble({ role, content, sources, isStreaming, reasoningSteps }) {
  const isUser = role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[720px] rounded-2xl border px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? "border-accent bg-accent text-white"
            : "border-border bg-surface text-text"
        }`}
      >
        {!isUser && reasoningSteps && reasoningSteps.length > 0 && (
          <ReasoningSteps steps={reasoningSteps} isStreaming={isStreaming} />
        )}
        <div className={isUser ? "text-white" : "text-text"}>
          {content ? (
            renderRichText(content)
          ) : isStreaming ? (
            <div className="flex items-center gap-2 text-muted">
              <Loader2 size={14} className="animate-spin" />
              <span>Generating response...</span>
            </div>
          ) : null}
          {isStreaming && content && (
            <span className="inline-block w-1 h-4 ml-0.5 bg-accent animate-pulse" />
          )}
        </div>
        {!isUser ? <SourceList sources={sources} /> : null}
      </div>
    </div>
  );
}
