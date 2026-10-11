import { Upload } from "lucide-react";

import { supportedUploadTypesLabel } from "../../../data/mockData";
import { Button } from "../../ui/Button";

export function UploadZone({ onBrowse }) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-bg p-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface text-muted">
            <Upload size={16} />
          </div>
          <div>
            <div className="text-sm font-medium text-text">
              Drag & drop files here, or click to select.
            </div>
            <div className="mt-1 text-xs text-muted">
              Supported: {supportedUploadTypesLabel}
            </div>
          </div>
        </div>
        <Button variant="primary" onClick={onBrowse}>
          Browse Files
        </Button>
      </div>
    </div>
  );
}
