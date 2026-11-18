import { useState } from "react";
import { describeApiError } from "../../../api/client";
import { useAppState } from "../../../state/AppStateContext";
import { Button } from "../../ui/Button";
import { DocumentPicker } from "./DocumentPicker";

export function UploadDocuments({ kbId, onUploaded }) {
  const { actions } = useAppState();
  const [files, setFiles] = useState([]);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  return <section aria-label="Add documents" className="rounded-lg border border-border bg-surface p-4">
    <h2 className="mb-3 text-sm font-semibold text-text">Add documents</h2>
    {error && <p role="alert" className="mb-3 whitespace-pre-line text-sm text-red-600 dark:text-red-300">{error}</p>}
    <DocumentPicker label="Add documents" files={files} onChange={setFiles} onError={setError} disabled={pending} />
    <div className="mt-3 flex justify-end"><Button variant="primary" disabled={pending || !files.length} onClick={async () => {
      setPending(true); setError("");
      try { await actions.uploadDocuments(kbId, files); setFiles([]); onUploaded("Documents uploaded. Processing status is shown below."); }
      catch (failure) { setError(describeApiError(failure)); }
      finally { setPending(false); }
    }}>{pending ? "Uploading…" : "Upload documents"}</Button></div>
  </section>;
}
