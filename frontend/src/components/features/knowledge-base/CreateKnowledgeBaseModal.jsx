import { ChevronDown } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { createId } from "../../../utils/id";
import { Input } from "../../ui/Input";
import { Modal } from "../../ui/Modal";
import { Button } from "../../ui/Button";
import { FileList } from "./FileList";
import { UploadZone } from "./UploadZone";

function fileExtension(name) {
  const idx = name.lastIndexOf(".");
  if (idx === -1) return "";
  return name.slice(idx + 1).toLowerCase();
}

export function CreateKnowledgeBaseModal({ open, onClose, onCreate }) {
  const [name, setName] = useState("");
  const [files, setFiles] = useState([]);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const inputRef = useRef(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const [rankingStrategy, setRankingStrategy] = useState("Hybrid");
  const [embeddingModel, setEmbeddingModel] = useState(
    "sentence-transformers/all-MiniLM-L6-v2"
  );
  const [chunkingStrategy, setChunkingStrategy] = useState("Recursive (800/120)");

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  const hasUploadedFile = useMemo(
    () => files.length > 0,
    [files]
  );

  const footer = (
    <div className="flex items-center justify-between gap-3">
      <div className="text-xs text-muted">Create is enabled after selecting files.</div>
      <div className="flex items-center gap-2">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button
          variant="primary"
          disabled={submitting || !hasUploadedFile || name.trim().length === 0}
          onClick={async () => {
            setError("");
            setSubmitting(true);
            try {
              await onCreate({
                name: name.trim(),
                rankingStrategy,
                embeddingModel,
                chunkingStrategy,
                files: files.map((f) => f.rawFile),
              });
              setName("");
              setFiles([]);
              setAdvancedOpen(false);
            } catch (e) {
              setError(e?.message || String(e));
            } finally {
              setSubmitting(false);
            }
          }}
        >
          {submitting ? "Creating…" : "Create"}
        </Button>
      </div>
    </div>
  );

  return (
    <Modal
      open={open}
      title="Create Knowledge Base"
      onClose={() => {
        onClose();
        setName("");
        setFiles([]);
        setAdvancedOpen(false);
      }}
      footer={footer}
    >
      <div className="space-y-4">
        {error ? (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-200">
            {error}
          </div>
        ) : null}
        <div>
          <div className="mb-2 text-xs font-semibold text-muted">Name</div>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g., Nvidia Q2 results"
          />
        </div>

        <div>
          <div className="mb-2 text-xs font-semibold text-muted">Upload</div>
          <input
            ref={inputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => {
              const chosen = Array.from(e.target.files || []);
              if (chosen.length === 0) return;

              if (name.trim().length === 0) {
                const first = chosen[0]?.name || "";
                const base = first.replace(/\.[^/.]+$/, "");
                if (base) setName(base);
              }

              setFiles((prev) => [
                ...prev,
                ...chosen.map((f) => ({
                  id: createId("upload"),
                  name: f.name,
                  type: fileExtension(f.name) || "txt",
                  size: f.size,
                  status: "UPLOADED",
                  progress: 100,
                  rawFile: f,
                })),
              ]);

              e.target.value = "";
            }}
          />
          <UploadZone
            onBrowse={() => {
              inputRef.current?.click();
            }}
          />
          <FileList files={files} />
        </div>

        <div className="rounded-lg border border-border bg-bg">
          <button
            type="button"
            onClick={() => setAdvancedOpen((v) => !v)}
            className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
          >
            <div>
              <div className="text-sm font-medium text-text">Advanced Settings</div>
              <div className="mt-0.5 text-xs text-muted">
                Ranking, embeddings, and chunking.
              </div>
            </div>
            <ChevronDown
              size={16}
              className={`text-muted transition-transform ${advancedOpen ? "rotate-180" : ""}`}
            />
          </button>

          {advancedOpen ? (
            <div className="grid gap-3 border-t border-border px-4 py-4 md:grid-cols-3">
              <label className="text-xs text-muted">
                <div className="mb-2 font-semibold">Ranking Strategy</div>
                <select
                  value={rankingStrategy}
                  onChange={(e) => setRankingStrategy(e.target.value)}
                  className="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/40"
                >
                  <option>Hybrid</option>
                  <option>BM25</option>
                  <option>Dense</option>
                </select>
              </label>

              <label className="text-xs text-muted">
                <div className="mb-2 font-semibold">Embedding Model</div>
                <select
                  value={embeddingModel}
                  onChange={(e) => setEmbeddingModel(e.target.value)}
                  className="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/40"
                >
                  <option>deterministic</option>
                  <option>text-embedding-3-small</option>
                  <option>text-embedding-3-large</option>
                  <option>sentence-transformers/all-MiniLM-L6-v2</option>
                </select>
              </label>

              <label className="text-xs text-muted">
                <div className="mb-2 font-semibold">Chunking Strategy</div>
                <select
                  value={chunkingStrategy}
                  onChange={(e) => setChunkingStrategy(e.target.value)}
                  className="h-10 w-full rounded-md border border-border bg-surface px-3 text-sm text-text focus:outline-none focus:ring-2 focus:ring-accent/40"
                >
                  <option>Recursive (800/120)</option>
                  <option>Fixed (512/64)</option>
                  <option>Semantic (auto)</option>
                </select>
              </label>
            </div>
          ) : null}
        </div>
      </div>
    </Modal>
  );
}
