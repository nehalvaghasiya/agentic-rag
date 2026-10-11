import { getFileIcon } from "../../../utils/fileIcons";
import { formatBytes } from "../../../utils/format";
import { ProgressBar } from "../../ui/ProgressBar";

export function FileList({ files }) {
  if (files.length === 0) return null;

  return (
    <div className="mt-3 space-y-2">
      {files.map((file) => {
        const Icon = getFileIcon(file.type);
        return (
          <div
            key={file.id}
            className="rounded-lg border border-border bg-bg px-4 py-3"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-3">
                <div className="mt-0.5 flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface text-muted">
                  <Icon size={16} />
                </div>
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-text">
                    {file.name}
                  </div>
                  <div className="mt-0.5 text-xs text-muted">
                    {formatBytes(file.size)} • {String(file.type).toUpperCase()}
                  </div>
                </div>
              </div>
              <div className="shrink-0 text-xs text-muted">{file.progress}%</div>
            </div>
            <div className="mt-3">
              <ProgressBar value={file.progress} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
