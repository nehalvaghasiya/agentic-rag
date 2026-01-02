import { useState } from "react";
import {
  Brain,
  ChevronDown,
  ChevronRight,
  FileSearch,
  Filter,
  Loader2,
  Search,
  Sparkles,
} from "lucide-react";

const stepIcons = {
  analyzing: Brain,
  generating_queries: Search,
  searching: FileSearch,
  grading: Filter,
  generating: Sparkles,
};

const stepLabels = {
  analyzing: "Analyzing",
  generating_queries: "Searching",
  searching: "Retrieving",
  grading: "Evaluating",
  generating: "Generating",
};

function StepItem({ step, isActive, isLast }) {
  const Icon = stepIcons[step.type] || Brain;
  const label = stepLabels[step.type] || step.title;

  return (
    <div className="flex items-start gap-2">
      <div
        className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${
          isActive
            ? "bg-accent text-white"
            : "bg-accent/10 text-accent"
        }`}
      >
        {isActive ? (
          <Loader2 size={12} className="animate-spin" />
        ) : (
          <Icon size={12} />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div
          className={`text-xs font-medium ${
            isActive ? "text-text" : "text-muted"
          }`}
        >
          {label}
        </div>
        <div className="text-xs text-muted/80 leading-relaxed">
          {step.description}
        </div>
        {step.details?.queries && (
          <div className="mt-1 flex flex-wrap gap-1">
            {step.details.queries.map((q, i) => (
              <span
                key={i}
                className="inline-block rounded bg-border/40 px-1.5 py-0.5 text-[10px] text-muted"
              >
                {q.length > 40 ? q.slice(0, 40) + "..." : q}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function ReasoningSteps({ steps, isStreaming }) {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!steps || steps.length === 0) {
    return null;
  }

  const activeStepIndex = steps.length - 1;

  return (
    <div className="mb-3 rounded-lg border border-border/60 bg-surface/50">
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-border/20 transition-colors rounded-lg"
      >
        {isExpanded ? (
          <ChevronDown size={14} className="text-muted" />
        ) : (
          <ChevronRight size={14} className="text-muted" />
        )}
        <Brain size={14} className="text-accent" />
        <span className="text-xs font-medium text-text">
          {isStreaming ? "Thinking..." : "Reasoning Steps"}
        </span>
        <span className="ml-auto text-[10px] text-muted">
          {steps.length} step{steps.length !== 1 ? "s" : ""}
        </span>
      </button>

      {isExpanded && (
        <div className="border-t border-border/40 px-3 py-2 space-y-2">
          {steps.map((step, index) => (
            <StepItem
              key={index}
              step={step}
              isActive={isStreaming && index === activeStepIndex}
              isLast={index === steps.length - 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
