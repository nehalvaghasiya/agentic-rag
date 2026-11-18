import { useEffect, useRef, useState } from "react";
import { describeApiError } from "../../../api/client";
import { getDocumentFile, getDocumentPreview } from "../../../api/chat";
import { Button } from "../../ui/Button";
import { Modal } from "../../ui/Modal";

export function DocumentPreview({ document: doc, onClose }) {
  const isPdf = doc.name.toLowerCase().endsWith(".pdf");
  const inlinePdf = isPdf && navigator.pdfViewerEnabled === true;
  const [mode, setMode] = useState(inlinePdf ? "pdf" : "text");
  const [offsets, setOffsets] = useState([0]);
  const [result, setResult] = useState(null);
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const offset = offsets.at(-1);
  useEffect(() => {
    const controller = new AbortController();
    let objectUrl;
    setLoading(true); setError(""); setResult(null); setUrl("");
    const load = async () => {
      try {
        if (mode === "pdf") {
          const file = await getDocumentFile(doc.id, doc.version, controller.signal);
          if (controller.signal.aborted) return;
          objectUrl = URL.createObjectURL(file); setUrl(objectUrl);
        } else {
          const preview = await getDocumentPreview(doc.id, doc.version, offset, controller.signal);
          if (!controller.signal.aborted) setResult(preview);
        }
      } catch (failure) { if (!controller.signal.aborted) setError(describeApiError(failure)); }
      finally { if (!controller.signal.aborted) setLoading(false); }
    };
    void load();
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [doc.id, doc.version, mode, offset, attempt]);
  return <Modal open wide title={`Preview: ${doc.name}`} onClose={onClose} footer={<div className="flex flex-wrap items-center justify-between gap-3">
    <div className="flex gap-2">{isPdf && <Button disabled={mode === "text"} onClick={() => setMode("text")}>View as text</Button>}
      {inlinePdf && <Button disabled={mode === "pdf"} onClick={() => setMode("pdf")}>View PDF</Button>}</div>
    {mode === "text" && <div className="flex items-center gap-2">
      <Button disabled={loading || offsets.length === 1} onClick={() => setOffsets(previous => previous.slice(0, -1))}>Previous</Button>
      <span className="text-xs text-muted">Page {offsets.length}</span>
      <Button disabled={loading || result?.next_offset == null} onClick={() => setOffsets(previous => [...previous, result.next_offset])}>Next</Button>
    </div>}
    <DownloadDocumentButton document={doc} />
  </div>}>
    {isPdf && !inlinePdf && <p className="mb-3 text-xs text-muted">Inline PDF viewing is unavailable in this browser. Showing extracted text; download the original to see its page layout.</p>}
    {loading && <p role="status" className="py-12 text-center text-muted">Loading preview…</p>}
    {error && <div role="alert" className="space-y-3 text-sm text-red-600 dark:text-red-300"><p className="whitespace-pre-line">{error}</p><Button onClick={() => setAttempt(value => value + 1)}>Retry preview</Button></div>}
    {url && <iframe title={`PDF preview of ${doc.name}`} src={url} className="h-[60vh] w-full rounded border border-border" onError={() => setError("The browser could not display this PDF. Use View as text or Download original.")} />}
    {result && <div className="space-y-4">
      <p className="text-xs text-muted">Characters {Math.min(offset + 1, result.total_characters).toLocaleString()}–{Math.min(result.next_offset ?? result.total_characters, result.total_characters).toLocaleString()} of {result.total_characters.toLocaleString()}</p>
      {result.sections.map((section, index) => <section key={index}>
        {(section.page || section.section) && <h3 className="mb-2 text-xs font-semibold text-muted">{section.page ? `Document page ${section.page}` : section.section}</h3>}
        <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-7 text-text">{section.text}</pre>
      </section>)}
    </div>}
  </Modal>;
}

export function DownloadDocumentButton({ document: doc }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const active = useRef(null);
  useEffect(() => () => active.current?.abort(), []);
  return <div><Button size="sm" disabled={pending} aria-label={`Download ${doc.name}`} onClick={async () => {
    const controller = new AbortController(); active.current = controller;
    setPending(true); setError("");
    try {
      const file = await getDocumentFile(doc.id, doc.version, controller.signal);
      if (controller.signal.aborted) return;
      const url = URL.createObjectURL(file);
      const link = window.document.createElement("a"); link.href = url; link.download = doc.name;
      window.document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (failure) { if (!controller.signal.aborted) setError(describeApiError(failure)); }
    finally { if (!controller.signal.aborted) setPending(false); }
  }}>{pending ? "Downloading…" : "Download original"}</Button>
    {error && <p role="alert" className="mt-2 max-w-sm whitespace-pre-line text-xs text-red-600 dark:text-red-300">{error}</p>}
  </div>;
}
