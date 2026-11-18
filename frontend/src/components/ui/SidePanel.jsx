import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

export function SidePanel({ title, docked = false, onClose, children }) {
  const id = useId();
  const panel = useRef(null);
  const heading = useRef(null);
  const close = useRef(onClose); close.current = onClose;
  useEffect(() => {
    const previous = document.activeElement;
    const root = document.getElementById("root");
    const wasInert = root?.inert;
    if (!docked && root) root.inert = true;
    heading.current?.focus();
    const keydown = event => {
      const dialogs = [...document.querySelectorAll('[aria-modal="true"]')];
      if (dialogs.length && !dialogs.at(-1).isSameNode(panel.current)) return;
      if (event.defaultPrevented) return;
      if (event.key === "Escape") { event.preventDefault(); close.current(); }
      if (!docked && event.key === "Tab") {
        const items = [...panel.current.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),[tabindex="0"]')];
        const first = items[0], last = items.at(-1);
        if (!items.length) { event.preventDefault(); heading.current?.focus(); }
        else if (event.shiftKey && (document.activeElement === first || document.activeElement === heading.current)) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      if (!docked && root) root.inert = wasInert;
      if (previous?.isConnected) previous.focus();
    };
  }, [docked]);
  const content = <aside ref={panel} role={docked ? "region" : "dialog"} aria-modal={docked ? undefined : true}
    aria-labelledby={id} className={docked ? "flex h-full w-[360px] shrink-0 flex-col border-l border-border bg-surface" :
      "fixed inset-0 z-50 flex flex-col bg-surface sm:inset-y-3 sm:left-auto sm:right-3 sm:w-[min(400px,calc(100vw-24px))] sm:rounded-2xl sm:border sm:border-border sm:shadow-xl"}>
    <header className="flex min-h-16 shrink-0 items-center justify-between gap-3 border-b border-border px-5 py-2">
      <h2 ref={heading} tabIndex={-1} id={id} className="text-base font-semibold text-text outline-none">{title}</h2>
      <button type="button" className="response-icon" aria-label={`Close ${title.toLowerCase()}`} title="Close" onClick={onClose}><X size={19} /></button>
    </header>
    <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-5">{children}</div>
  </aside>;
  return docked ? content : createPortal(<><div className="fixed inset-0 z-40 bg-black/40" aria-hidden="true" onClick={onClose} />{content}</>, document.body);
}
