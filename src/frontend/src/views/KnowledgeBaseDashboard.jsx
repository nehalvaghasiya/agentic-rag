import { Trash2 } from "lucide-react";
import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { StatGrid } from "../components/features/knowledge-base/StatGrid";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useAppState } from "../state/AppStateContext";
import { getFileIcon } from "../utils/fileIcons";
import { formatBytes } from "../utils/format";

export function KnowledgeBaseDashboard() {
  const { kbId } = useParams();
  const navigate = useNavigate();
  const { knowledgeBases, actions } = useAppState();

  const kb = knowledgeBases.find((k) => k.id === kbId);
  const stats = useMemo(() => (kb ? actions.computeKbStats(kb) : null), [kb, actions]);

  if (!kb || !stats) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted">
        Knowledge base not found.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-border bg-bg px-6 py-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="text-lg font-semibold text-text">{kb.name}</div>
            <div className="mt-1 text-sm text-muted">Knowledge Base Dashboard</div>
          </div>
          <Button
            variant="ghost"
            onClick={() => {
              actions.deleteKnowledgeBase(kb.id);
              navigate("/");
            }}
            className="border border-border bg-surface"
          >
            <Trash2 size={16} className="text-muted" />
            Delete
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-auto px-6 py-6">
        <StatGrid stats={stats} />

        <div className="mt-6">
          <div className="mb-3 text-xs font-semibold text-muted">Files</div>
          <Card className="overflow-hidden">
            <div className="grid grid-cols-12 gap-3 border-b border-border bg-surface px-4 py-3 text-xs font-semibold text-muted">
              <div className="col-span-1">&nbsp;</div>
              <div className="col-span-6">Name</div>
              <div className="col-span-2">Size</div>
              <div className="col-span-2">Status</div>
              <div className="col-span-1 text-right">&nbsp;</div>
            </div>

            <div className="divide-y divide-border">
              {kb.documents.map((doc) => {
                const Icon = getFileIcon(doc.type);
                return (
                  <div
                    key={doc.id}
                    className="grid grid-cols-12 items-center gap-3 px-4 py-3"
                  >
                    <div className="col-span-1 text-muted">
                      <Icon size={16} />
                    </div>
                    <div className="col-span-6 min-w-0">
                      <div className="truncate text-sm text-text">{doc.name}</div>
                      <div className="mt-0.5 text-xs text-muted">
                        {String(doc.type).toUpperCase()}
                      </div>
                    </div>
                    <div className="col-span-2 text-sm text-muted">
                      {formatBytes(doc.size)}
                    </div>
                    <div className="col-span-2">
                      <span className="inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-xs font-medium text-emerald-300">
                        {doc.status}
                      </span>
                    </div>
                    <div className="col-span-1 flex justify-end">
                      <button
                        type="button"
                        onClick={() => actions.deleteDocument(kb.id, doc.id)}
                        className="rounded-md border border-border bg-bg p-2 text-muted hover:bg-border/30"
                        aria-label="Delete file"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
