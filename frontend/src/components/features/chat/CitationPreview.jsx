import { renderHighlightedText } from "../../../utils/highlight";

export function CitationPreview({ source }) {
  const parts = renderHighlightedText(source.snippetText, source.highlight);
  const meta = source.metadata || {};
  const metaLine = Object.entries(meta)
    .filter(([k, v]) => v !== null && v !== undefined && String(v).length > 0)
    .filter(([k]) => k !== "source" && k !== "page")
    .slice(0, 3)
    .map(([k, v]) => `${k}=${String(v)}`)
    .join(" • ");

  const locationLabel =
    source.pageNumber != null
      ? `Page ${source.pageNumber}`
      : source.chunkIndex != null
        ? `Chunk ${source.chunkIndex}`
        : "Chunk";

  return (
    <div className="w-80 rounded-lg border border-border bg-surface p-3 shadow-none">
      <div className="text-xs font-semibold text-text">
        {source.fileName} • {locationLabel}
      </div>
      {metaLine ? (
        <div className="mt-1 text-[11px] text-muted">{metaLine}</div>
      ) : null}
      <div className="mt-2 text-xs leading-relaxed text-muted">
        {parts.map((p, idx) =>
          p.highlight ? (
            <mark
              key={idx}
              className="rounded bg-yellow-400/15 px-0.5 text-yellow-200"
            >
              {p.text}
            </mark>
          ) : (
            <span key={idx}>{p.text}</span>
          )
        )}
      </div>
    </div>
  );
}
