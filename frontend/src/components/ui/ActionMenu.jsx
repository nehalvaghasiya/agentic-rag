import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MoreHorizontal } from "lucide-react";

export function ActionMenu({ label = "More options", items, disabled = false }) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const trigger = useRef(null);
  const menu = useRef(null);
  const id = useId();
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const rect = trigger.current.getBoundingClientRect();
      const height = menu.current?.offsetHeight || 180;
      setPosition({ left: Math.max(8, Math.min(rect.left, window.innerWidth - 248)),
        top: rect.bottom + height + 8 < window.innerHeight ? rect.bottom + 4 : Math.max(8, rect.top - height - 4) });
    };
    place(); menu.current?.querySelector('[role="menuitem"]')?.focus();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => { window.removeEventListener("resize", place); window.removeEventListener("scroll", place, true); };
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const outside = event => {
      if (!menu.current?.contains(event.target) && !trigger.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open]);
  const close = () => { setOpen(false); trigger.current?.focus(); };
  return <>
    <button ref={trigger} type="button" className="response-icon" title={label} aria-label={label}
      aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined} disabled={disabled}
      onClick={() => setOpen(value => !value)} onKeyDown={event => {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") { event.preventDefault(); setOpen(true); }
      }}><MoreHorizontal size={18} /></button>
    {open && createPortal(<div ref={menu} id={id} role="menu" aria-label={label} style={position}
      className="fixed z-[70] w-60 max-h-[calc(100dvh-16px)] overflow-auto rounded-xl border border-border bg-surface p-1.5 shadow-xl"
      onKeyDown={event => {
        const controls = [...menu.current.querySelectorAll('[role="menuitem"]')];
        const at = controls.indexOf(document.activeElement);
        if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
          event.preventDefault();
          const next = event.key === "Home" ? 0 : event.key === "End" ? controls.length - 1 :
            (at + (event.key === "ArrowDown" ? 1 : -1) + controls.length) % controls.length;
          controls[next]?.focus();
        }
        if (event.key === "Escape") { event.preventDefault(); close(); }
        if (event.key === "Tab") {
          event.preventDefault();
          const controls = [...document.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),[tabindex="0"]')]
            .filter(element => !menu.current.contains(element) && !element.closest("[inert]"));
          const next = controls.indexOf(trigger.current) + (event.shiftKey ? -1 : 1);
          close(); controls[next]?.focus();
        }
      }}>
      {items.map(({ label: itemLabel, icon: Icon, onSelect }) => <button key={itemLabel} type="button" role="menuitem"
        className="flex min-h-11 w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-text hover:bg-border/40 focus-visible:bg-border/40 focus-visible:outline-none"
        onClick={() => { close(); onSelect(); }}>{Icon && <Icon size={16} className="shrink-0 text-muted" />}{itemLabel}</button>)}
    </div>, document.body)}
  </>;
}
