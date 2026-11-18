import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { BrainCircuit, Check, ChevronDown, Cpu, Database, FolderOpen, Loader2, MessageCircle, Search, SendHorizontal, Settings2, Square } from "lucide-react";

function SelectionPicker({ label, value, text, icon: Icon, items, onChange, disabled, searchable = false, loading = false, error, onRetry, footer }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [pending, setPending] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [active, setActive] = useState(value);
  const [position, setPosition] = useState({ left: 12, top: 12, width: 320, maxHeight: 420 });
  const trigger = useRef(null);
  const panel = useRef(null);
  const search = useRef(null);
  const restoreFocus = useRef(false);
  const id = useId();
  const filtered = items.filter(item => item.label.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
  const focusValue = filtered.some(item => item.value === active) ? active : filtered[0]?.value;
  const close = (restore = true) => {
    restoreFocus.current = restore;
    setOpen(false);
    if (restore && trigger.current?.isConnected && !trigger.current.disabled) {
      restoreFocus.current = false; trigger.current.focus();
    }
  };
  useEffect(() => {
    if (!open && !pending && !disabled && restoreFocus.current) {
      restoreFocus.current = false; trigger.current?.focus();
    }
  }, [open, pending, disabled]);
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      if (!trigger.current || !panel.current) return;
      const viewport = window.visualViewport;
      const topEdge = viewport?.offsetTop || 0;
      const height = viewport?.height || window.innerHeight;
      const width = Math.min(340, (viewport?.width || window.innerWidth) - 24);
      const rect = trigger.current.getBoundingClientRect();
      const anchor = trigger.current.closest(".chat-composer")?.getBoundingClientRect() || rect;
      const above = anchor.top - topEdge - 12;
      const below = topEdge + height - anchor.bottom - 12;
      const maxHeight = Math.max(0, Math.min(420, height - 24, Math.max(above, below) - 6));
      const actualHeight = Math.min(panel.current.offsetHeight, maxHeight);
      const top = above >= actualHeight || above > below ? anchor.top - actualHeight - 6 : anchor.bottom + 6;
      const next = { width, maxHeight, left: Math.max(12, Math.min(rect.left, window.innerWidth - width - 12)),
        top: Math.max(topEdge + 12, Math.min(top, topEdge + height - actualHeight - 12)) };
      setPosition(previous => Object.keys(next).every(key => previous[key] === next[key]) ? previous : next);
    };
    place();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(place) : null;
    observer?.observe(panel.current);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    window.visualViewport?.addEventListener("resize", place);
    return () => {
      observer?.disconnect(); window.removeEventListener("resize", place); window.removeEventListener("scroll", place, true);
      window.visualViewport?.removeEventListener("resize", place);
    };
  }, [open]);
  useEffect(() => {
    if (!open) return;
    (search.current || panel.current?.querySelector('[role="option"][tabindex="0"]') || panel.current)?.focus();
    const outside = event => {
      if (!panel.current?.contains(event.target) && !trigger.current?.contains(event.target)) setOpen(false);
    };
    const focus = event => {
      if (!panel.current?.contains(event.target) && !trigger.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("focusin", focus);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("focusin", focus); };
  }, [open]);
  useEffect(() => { if (disabled && !pending) setOpen(false); }, [disabled, pending]);
  const select = async item => {
    if (pending || disabled) return;
    if (item.value === value) { close(); return; }
    setPending(true); setSaveError("");
    try {
      const result = await onChange(item.value);
      if (result === false) { setSaveError("Couldn’t update your selection. Please try again.");
        requestAnimationFrame(() => (search.current || panel.current)?.focus()); return; }
      const restore = panel.current?.contains(document.activeElement) || document.activeElement === document.body;
      close(restore);
    } catch { setSaveError("Couldn’t update your selection. Please try again."); requestAnimationFrame(() => (search.current || panel.current)?.focus()); }
    finally { setPending(false); }
  };
  const keyboard = event => {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); close(); return; }
    const options = [...panel.current.querySelectorAll('[role="option"]:not([disabled])')];
    const inSearch = event.target === search.current;
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key) && (!inSearch || event.key.startsWith("Arrow"))) {
      event.preventDefault();
      const at = options.indexOf(document.activeElement);
      const next = event.key === "Home" ? 0 : event.key === "End" ? options.length - 1 : inSearch ?
        event.key === "ArrowDown" ? 0 : options.length - 1 : (at + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
      options[next]?.focus();
    }
    if (event.key === "Tab") {
      const focusable = [...panel.current.querySelectorAll('input:not([disabled]),button:not([disabled]):not([tabindex="-1"]),a[href]')];
      if (!focusable.length || (event.shiftKey && document.activeElement === focusable[0]) || (!event.shiftKey && document.activeElement === focusable.at(-1))) {
        event.preventDefault();
        const controls = [...document.querySelectorAll('button:not([disabled]),input:not([disabled]),textarea:not([disabled]),a[href],[tabindex="0"]')]
          .filter(element => !panel.current.contains(element) && !element.closest("[inert]") && element.tabIndex >= 0);
        const next = controls.indexOf(trigger.current) + (event.shiftKey ? -1 : 1);
        close(false); controls[next]?.focus();
      }
    }
  };
  return <>
    <button ref={trigger} type="button" className="composer-control min-w-0 flex-1" aria-label={label}
      aria-description={`Selected: ${searchable && value === "" ? "General chat" : text}`} data-selected={value !== ""}
      title={`${label}: ${searchable && value === "" ? "General chat" : text}`} aria-haspopup="dialog" aria-expanded={open}
      aria-controls={open ? id : undefined} disabled={disabled || pending} onClick={() => {
        setQuery(""); setSaveError(""); setActive(value); setOpen(previous => !previous);
      }} onKeyDown={event => {
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
          event.preventDefault(); setQuery(""); setActive(value); setOpen(true);
        }
      }}>
      {pending ? <Loader2 size={16} aria-hidden="true" className="shrink-0 animate-spin motion-reduce:animate-none" /> : <Icon size={16} aria-hidden="true" className="shrink-0" />}
      <span className="truncate">{text}</span><ChevronDown size={12} aria-hidden="true" className={`ml-auto shrink-0 text-muted ${open ? "rotate-180" : ""}`} />
    </button>
    {open && createPortal(<div ref={panel} id={id} role="dialog" tabIndex={-1} aria-label={label} style={position} onKeyDown={keyboard}
      className="composer-picker fixed z-[70] flex flex-col overflow-hidden rounded-2xl border border-border bg-surface shadow-xl">
      <div className="flex shrink-0 items-center gap-2 px-4 pb-2 pt-4 text-xs font-semibold text-muted"><Icon size={14} aria-hidden="true" />{label.replace("Choose ", "").replace(/^./, character => character.toUpperCase())}</div>
      {searchable && <div className="relative mx-2 mb-2 shrink-0">
        <Search size={15} aria-hidden="true" className="pointer-events-none absolute left-3 top-3.5 text-muted" />
        <input ref={search} type="search" aria-label="Search knowledge bases" placeholder="Search knowledge bases…" value={query}
          disabled={pending} onChange={event => setQuery(event.target.value)}
          className="h-11 w-full rounded-xl border border-border bg-bg pl-9 pr-3 text-sm text-text outline-none focus-visible:ring-2 focus-visible:ring-accent/40" />
      </div>}
      <div className="min-h-0 overflow-y-auto overscroll-contain p-1.5" role="listbox" aria-label={searchable ? "Knowledge bases" : "Models"} aria-busy={pending || loading}>
        {filtered.map(item => {
          const ItemIcon = item.icon || Icon;
          return <button type="button" role="option" aria-label={item.label} aria-selected={item.value === value}
            aria-description={item.description || undefined} key={item.value} tabIndex={item.value === focusValue ? 0 : -1}
            disabled={disabled || pending} onFocus={() => setActive(item.value)} onClick={() => void select(item)}
            className="composer-option flex min-h-12 w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm text-text disabled:opacity-50">
            <ItemIcon size={17} aria-hidden="true" className="shrink-0 text-muted" />
            <span className="min-w-0 flex-1"><span className="block break-words font-medium">{item.label}</span>
              {item.description && <span className="mt-0.5 block text-xs font-normal text-muted">{item.description}</span>}</span>
            {item.badge && <span className="rounded-md bg-border/40 px-1.5 py-1 text-[10px] text-muted">{item.badge}</span>}
            <span className="flex w-4 shrink-0 items-center justify-center">{item.value === value && <Check size={16} className="text-accent" aria-hidden="true" />}</span>
          </button>;
        })}
        {loading && <p role="status" className="px-3 py-4 text-sm text-muted">Loading knowledge bases…</p>}
        {!loading && !error && (!filtered.length || (!query.trim() && searchable && !items.some(item => item.searchable !== false))) &&
          <p className="px-3 py-4 text-sm text-muted">{query.trim() ? "No knowledge bases match your search." : searchable ? "No knowledge bases yet. Open the library to add one." : "No models available."}</p>}
      </div>
      {(error || saveError) && <div role="alert" className="shrink-0 px-4 py-3 text-xs text-text">
        <p>{saveError || "Knowledge bases couldn’t be loaded."}</p>
        {error && onRetry && <button type="button" className="min-h-11 text-accent underline" onClick={onRetry}>Retry loading</button>}
      </div>}
      {footer && <div className="shrink-0 border-t border-border p-1.5">{footer}</div>}
    </div>, document.body)}
  </>;
}

function modelName(model) {
  return model?.name === "auto/best-fast" ? "Auto · Best fast" : model?.name || "Model";
}

export function ChatComposer({ value, onValueChange, onSubmit, onStop, knowledgeBases = [], kbId, onKnowledgeBaseChange,
  knowledgeLoading, knowledgeFailure, onRetryKnowledge, modelConfigs = [], selectedModelId, onModelChange,
  deep, onDeepChange, hydrated, busy, generating, canStop, versionBusy }) {
  const input = useRef(null);
  const [savingKnowledge, setSavingKnowledge] = useState(false);
  const knowledge = knowledgeBases.find(base => base.id === kbId);
  const model = modelConfigs.find(item => item.id === selectedModelId);
  const controlsDisabled = busy || !hydrated || savingKnowledge;
  useLayoutEffect(() => {
    if (!input.current) return;
    input.current.style.height = "auto";
    input.current.style.height = `${Math.max(44, Math.min(input.current.scrollHeight, 160))}px`;
  }, [value]);
  useEffect(() => {
    if (typeof ResizeObserver === "undefined") return;
    let width = 0;
    const observer = new ResizeObserver(entries => {
      const next = entries[0]?.contentRect.width;
      if (!input.current || width === next) return;
      width = next;
      input.current.style.height = "auto";
      input.current.style.height = `${Math.max(44, Math.min(input.current.scrollHeight, 160))}px`;
    });
    observer.observe(input.current);
    return () => observer.disconnect();
  }, []);
  const submit = event => {
    event.preventDefault();
    if (!controlsDisabled && value.trim()) onSubmit(event);
  };
  const chooseKnowledge = async id => {
    setSavingKnowledge(true);
    try { return await onKnowledgeBaseChange(id || null); }
    finally { setSavingKnowledge(false); }
  };
  const knowledgeItems = [
    { value: "", label: "General chat", description: "No knowledge base", icon: MessageCircle, searchable: false },
    ...knowledgeBases.map(base => {
      const documents = base.documents || [];
      const processing = documents.some(doc => ["processing", "queued", "running"].includes(doc.status));
      return { value: base.id, label: base.name, description: `${documents.length} ${documents.length === 1 ? "document" : "documents"}${processing ? " · Indexing" : ""}` };
    }),
  ];
  return <form onSubmit={submit} className="chat-composer mx-auto w-full max-w-[800px] rounded-2xl border border-border bg-surface p-3">
    <textarea ref={input} rows={1} aria-label="Message" aria-description="Enter to send. Shift+Enter for a new line."
      disabled={!hydrated || versionBusy} value={value} onChange={event => onValueChange(event.target.value)} placeholder="Ask a question…" maxLength={4000}
      className="composer-message block min-h-11 max-h-40 w-full resize-none bg-transparent px-2 py-2 text-base leading-7 text-text outline-none placeholder:text-muted"
      onKeyDown={event => {
        if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
          event.preventDefault(); submit(event);
        }
      }} />
    <div className="composer-toolbar mt-2">
      <div className="composer-knowledge min-w-0">
        <SelectionPicker label="Choose knowledge base" value={kbId || ""} text={knowledge?.name || "Knowledge base"} icon={Database}
          items={knowledgeItems} onChange={chooseKnowledge} disabled={controlsDisabled} searchable
          loading={knowledgeLoading && !knowledgeBases.length} error={knowledgeFailure} onRetry={onRetryKnowledge}
          footer={<Link to="/kb" className="composer-option flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm text-text"><FolderOpen size={16} aria-hidden="true" />Manage knowledge bases</Link>} />
        {kbId && <Link to={`/kb/${kbId}`} className="composer-manage" aria-label="Manage knowledge base" title={`Manage ${knowledge?.name || "knowledge base"}`}>
          <Settings2 size={16} aria-hidden="true" />
        </Link>}
      </div>
      <div className="composer-model min-w-0">
        <SelectionPicker label="Choose model" value={selectedModelId} text={modelName(model)} icon={Cpu}
          items={modelConfigs.map(item => ({ value: item.id, label: modelName(item), badge: item.demo ? "Demo" : undefined }))}
          onChange={onModelChange} disabled={controlsDisabled} />
      </div>
      <button type="button" className={`composer-control composer-analysis ${deep ? "is-active" : ""}`} aria-label="Deep analysis" aria-pressed={deep}
        title={deep ? "Deep analysis is on. More thorough answers may take longer." : "Use deep analysis for more thorough answers. May take longer."}
        disabled={controlsDisabled} onClick={() => onDeepChange(!deep)}>
        <BrainCircuit size={16} aria-hidden="true" className="shrink-0" /><span>Deep analysis</span>
        <span className="flex w-3 shrink-0 justify-center">{deep && <Check size={12} aria-hidden="true" />}</span>
      </button>
      {generating ? <button type="button" className="composer-submit is-stopping" aria-label="Stop" title="Stop response" disabled={!canStop} onClick={onStop}>
        <Square size={15} fill="currentColor" strokeWidth={0} aria-hidden="true" />
      </button> : <button type="submit" className="composer-submit" aria-label="Send" title="Send message" disabled={!value.trim() || controlsDisabled}>
        <SendHorizontal size={20} strokeWidth={2} aria-hidden="true" />
      </button>}
    </div>
  </form>;
}
