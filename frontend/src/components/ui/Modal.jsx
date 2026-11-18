import { AnimatePresence, motion as Motion } from "framer-motion";
import { useEffect, useId, useRef } from "react";

export function Modal({ open, title, onClose, children, footer, wide = false, busy = false }) {
  const titleId = useId();
  const panel = useRef(null);
  const close = useRef(onClose); close.current = onClose;
  const pending = useRef(busy); pending.current = busy;
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement;
    const element = panel.current;
    const background = [];
    for (let current = element.parentElement; current?.parentElement && current.parentElement !== document.body; current = current.parentElement) {
      for (const sibling of current.parentElement.children) {
        if (sibling !== current) { background.push([sibling, sibling.inert]); sibling.inert = true; }
      }
    }
    const controls = () => [...element.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled]),a[href],iframe,[tabindex="0"]')];
    (element.querySelector('[data-autofocus]') || controls()[0] || element).focus();
    const keydown = event => {
      if (event.key === "Escape") { event.preventDefault(); if (!pending.current) close.current(); }
      if (event.key !== "Tab") return;
      const items = controls();
      const first = items[0], last = items.at(-1);
      if (!first) { event.preventDefault(); element.focus(); }
      else if (event.shiftKey && (document.activeElement === first || !element.contains(document.activeElement))) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !element.contains(document.activeElement))) {
        event.preventDefault(); first.focus();
      }
    };
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      for (const [sibling, inert] of background) sibling.inert = inert;
      if (previous?.isConnected) previous.focus();
    };
  }, [open]);
  return <AnimatePresence>{open && <Motion.div className="fixed inset-0 z-50 flex items-center justify-center"
    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
    <div className="absolute inset-0 bg-black/60" onClick={() => { if (!busy) onClose(); }} aria-hidden="true" />
    <Motion.div ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-busy={busy} tabIndex={-1}
      className={`relative mx-4 w-full ${wide ? "max-w-5xl" : "max-w-2xl"} overflow-hidden rounded-xl border border-border bg-surface shadow-xl`}
      initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 12 }} transition={{ duration: 0.18 }}>
      <div className="flex items-center justify-between gap-4 border-b border-border px-5 py-4">
        <h2 id={titleId} className="min-w-0 truncate text-sm font-semibold text-text">{title}</h2>
        <button type="button" disabled={busy} onClick={onClose} aria-label="Close dialog" className="rounded border border-border px-3 py-1 text-xs text-text disabled:opacity-50">Close</button>
      </div>
      <div className="max-h-[75vh] overflow-auto px-5 py-4">{children}</div>
      {footer && <div className="border-t border-border px-5 py-4">{footer}</div>}
    </Motion.div>
  </Motion.div>}</AnimatePresence>;
}
