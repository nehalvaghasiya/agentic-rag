import { ChevronDown, ChevronRight, FileText, Hash, BookOpen, Target } from "lucide-react";
import { useState } from "react";
import { renderHighlightedText } from "../../../utils/highlight";

function SourceCard({ source, index, isExpanded, onToggle }) {
  const parts = renderHighlightedText(source.snippetText || "", source.highlight);
  const meta = source.metadata || {};
  
  // Format the location label
  const locationLabel =
    source.pageNumber != null
      ? `Page ${source.pageNumber}`
      : source.chunkIndex != null
        ? `Section ${source.chunkIndex + 1}`
        : `Source ${index + 1}`;

  // Get similarity score color based on value
  const getScoreColor = (score) => {
    if (score >= 80) return "text-green-400 bg-green-400/10";
    if (score >= 60) return "text-yellow-400 bg-yellow-400/10";
    return "text-orange-400 bg-orange-400/10";
  };

  // Get meaningful metadata entries (exclude internal fields)
  const metaEntries = Object.entries(meta)
    .filter(([k, v]) => v !== null && v !== undefined && String(v).length > 0)
    .filter(([k]) => !["source", "page", "chunk_index", "similarity_score", "page_label"].includes(k))
    .slice(0, 5);

  return (
    <div className="group overflow-hidden rounded-lg border border-border bg-surface/50 transition-all duration-200 hover:border-primary/30 hover:bg-surface">
      {/* Clickable header */}
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors"
      >
        {/* Expand/collapse icon */}
        <div className="flex-shrink-0 text-muted transition-transform duration-200">
          {isExpanded ? (
            <ChevronDown size={16} className="text-primary" />
          ) : (
            <ChevronRight size={16} />
          )}
        </div>

        {/* File icon */}
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
          <FileText size={16} />
        </div>

        {/* File info */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium text-text">
              {source.fileName || "Unknown file"}
            </span>
            <span className="flex-shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
              {locationLabel}
            </span>
            {source.score != null && (
              <span className={`flex-shrink-0 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${getScoreColor(source.score)}`}>
                <Target size={10} />
                {source.score}%
              </span>
            )}
          </div>
          {!isExpanded && source.snippetText && (
            <p className="mt-0.5 truncate text-xs text-muted">
              {source.snippetText.slice(0, 80)}...
            </p>
          )}
        </div>

        {/* Source number badge */}
        <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-bg text-xs font-semibold text-muted">
          {index + 1}
        </div>
      </button>

      {/* Expandable content */}
      <div
        className={`overflow-hidden transition-all duration-300 ease-in-out ${
          isExpanded ? "max-h-96 opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="border-t border-border/50 px-4 pb-4 pt-3">
          {/* Snippet text with highlighting */}
          <div className="rounded-md bg-bg/50 p-3">
            <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted">
              <BookOpen size={12} />
              <span>Excerpt</span>
            </div>
            <p className="text-sm leading-relaxed text-text/90">
              {parts.map((p, idx) =>
                p.highlight ? (
                  <mark
                    key={idx}
                    className="rounded bg-yellow-400/20 px-0.5 text-yellow-200"
                  >
                    {p.text}
                  </mark>
                ) : (
                  <span key={idx}>{p.text}</span>
                )
              )}
            </p>
          </div>

          {/* Metadata */}
          {metaEntries.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {metaEntries.map(([key, value]) => (
                <div
                  key={key}
                  className="inline-flex items-center gap-1 rounded-md bg-bg px-2 py-1 text-xs"
                >
                  <Hash size={10} className="text-muted" />
                  <span className="text-muted">{key}:</span>
                  <span className="font-medium text-text">{String(value)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function SourceList({ sources }) {
  const [expandedSources, setExpandedSources] = useState(new Set());
  const [isCollapsed, setIsCollapsed] = useState(false);

  if (!sources || sources.length === 0) return null;

  const toggleSource = (index) => {
    setExpandedSources((prev) => {
      const next = new Set(prev);
      if (next.has(index)) {
        next.delete(index);
      } else {
        next.add(index);
      }
      return next;
    });
  };

  const expandAll = () => {
    setExpandedSources(new Set(sources.map((_, i) => i)));
  };

  const collapseAll = () => {
    setExpandedSources(new Set());
  };

  return (
    <div className="mt-4">
      {/* Header with toggle */}
      <button
        type="button"
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="group flex w-full items-center gap-2 rounded-md px-1 py-1.5 text-left transition-colors hover:bg-border/20"
      >
        <div className="text-muted transition-transform duration-200">
          {isCollapsed ? (
            <ChevronRight size={14} />
          ) : (
            <ChevronDown size={14} />
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-muted">Sources</span>
          <span className="rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-primary">
            {sources.length}
          </span>
        </div>
        {!isCollapsed && (
          <div className="ml-auto flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                expandAll();
              }}
              className="rounded px-1.5 py-0.5 text-[10px] text-muted hover:bg-border/30 hover:text-text"
            >
              Expand all
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                collapseAll();
              }}
              className="rounded px-1.5 py-0.5 text-[10px] text-muted hover:bg-border/30 hover:text-text"
            >
              Collapse all
            </button>
          </div>
        )}
      </button>

      {/* Source cards */}
      <div
        className={`mt-2 space-y-2 overflow-hidden transition-all duration-300 ease-in-out ${
          isCollapsed ? "max-h-0 opacity-0" : "max-h-[2000px] opacity-100"
        }`}
      >
        {sources.map((source, index) => (
          <SourceCard
            key={`${source.fileName}-${source.pageNumber ?? "np"}-${source.chunkIndex ?? index}`}
            source={source}
            index={index}
            isExpanded={expandedSources.has(index)}
            onToggle={() => toggleSource(index)}
          />
        ))}
      </div>
    </div>
  );
}
