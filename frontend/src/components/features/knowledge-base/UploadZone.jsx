import { Upload } from "lucide-react";
import { Button } from "../../ui/Button";
import { supportedTypes } from "./uploadRules";

export function UploadZone({ onBrowse, onFiles, disabled = false }) {
  return <div className="rounded-lg border border-dashed border-border bg-bg p-4"
    onDragOver={event => { event.preventDefault(); }}
    onDrop={event => { event.preventDefault(); if (!disabled) onFiles?.(Array.from(event.dataTransfer.files)); }}>
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-start gap-3"><Upload size={20} className="mt-1 shrink-0 text-muted" />
        <div><p className="text-sm font-medium text-text">Drag files here, or browse to select.</p>
          <p className="mt-1 text-xs text-muted">{supportedTypes} · Up to 10 files · 8 MiB each</p></div>
      </div>
      <Button disabled={disabled} onClick={onBrowse}>Browse Files</Button>
    </div>
  </div>;
}
