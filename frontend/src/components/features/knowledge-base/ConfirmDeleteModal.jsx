import { useState } from "react";
import { describeApiError } from "../../../api/client";
import { Button } from "../../ui/Button";
import { Modal } from "../../ui/Modal";

export function ConfirmDeleteModal({ target, onConfirm, onClose }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  return <Modal open title={target.kind === "knowledge" ? "Delete knowledge base" : "Delete document"} busy={pending} onClose={onClose}
    footer={<div className="flex justify-end gap-2"><Button data-autofocus disabled={pending} onClick={onClose}>Cancel</Button>
      <Button className="border-red-500/50 text-red-600 dark:text-red-300" disabled={pending} onClick={async () => {
        setPending(true); setError("");
        try { await onConfirm(); onClose(); } catch (failure) { setError(describeApiError(failure)); setPending(false); }
      }}>{pending ? "Deleting…" : "Confirm delete"}</Button></div>}>
    <p className="text-sm text-text">Delete <strong className="break-words">{target.name}</strong>?</p>
    <p className="mt-3 text-sm text-muted">{target.kind === "knowledge"
      ? `This permanently removes this knowledge base and its ${target.count} document${target.count === 1 ? "" : "s"}. Attached chats will be detached; conversations remain accessible.`
      : "This permanently removes the original file and its indexed content. The knowledge base and its other documents remain accessible."}</p>
    <p className="mt-2 text-xs text-muted">Answers relying on deleted sources will be marked unavailable.</p>
    {error && <p role="alert" className="mt-4 whitespace-pre-line text-sm text-red-600 dark:text-red-300">{error}</p>}
  </Modal>;
}
