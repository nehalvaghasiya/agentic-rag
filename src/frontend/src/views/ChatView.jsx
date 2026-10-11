import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Database, X, ChevronDown } from "lucide-react";

import { ChatBubble } from "../components/features/chat/ChatBubble";
import { ModelSelector } from "../components/features/chat/ModelSelector";
import { Button } from "../components/ui/Button";
import { useAppState } from "../state/AppStateContext";

export function ChatView() {
  const { chatId } = useParams();
  const { chatHistory, knowledgeBases, modelConfigs, selectedModelId, actions } = useAppState();
  const [value, setValue] = useState("");
  const [showKbDropdown, setShowKbDropdown] = useState(false);
  const dropdownRef = useRef(null);

  const chat = chatHistory.find((c) => c.id === chatId);
  const kb = useMemo(
    () => knowledgeBases.find((k) => k.id === chat?.kbId) ?? null,
    [knowledgeBases, chat]
  );

  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [chat?.messages?.length]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowKbDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!chat) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted">
        Chat not found.
      </div>
    );
  }

  const handleSend = () => {
    if (!value.trim()) return;
    actions.sendMessage(chat.id, value);
    setValue("");
  };

  const handleSelectKb = (kbId) => {
    actions.setChatKnowledgeBase(chat.id, kbId);
    setShowKbDropdown(false);
    inputRef.current?.focus();
  };

  const handleRemoveKb = (e) => {
    e.stopPropagation();
    actions.setChatKnowledgeBase(chat.id, null);
  };

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="border-b border-border bg-bg px-6 py-4">
        <div className="text-sm font-semibold text-text">{chat.title}</div>
        {kb && (
          <div className="mt-1 text-xs text-muted">
            Using knowledge base for citations
          </div>
        )}
      </div>

      <div className="flex-1 overflow-auto px-6 py-6">
        <div className="space-y-3">
          {chat.messages.map((m) => (
            <ChatBubble
              key={m.id}
              role={m.role}
              content={m.content}
              sources={m.sources}
              isStreaming={m.isStreaming}
              reasoningSteps={m.reasoningSteps}
            />
          ))}
          <div ref={endRef} />
        </div>
      </div>

      <div className="border-t border-border bg-bg px-6 py-4">
        {/* KB attachment chip when selected */}
        {kb && (
          <div className="mb-2 flex items-center">
            <div className="inline-flex items-center gap-1.5 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs text-accent">
              <Database size={12} />
              <span>{kb.name}</span>
              <button
                type="button"
                onClick={handleRemoveKb}
                className="ml-1 rounded-full p-0.5 hover:bg-accent/20"
                title="Remove knowledge base"
              >
                <X size={12} />
              </button>
            </div>
          </div>
        )}

        <div className="flex items-center gap-2">
          {/* KB attachment button with dropdown */}
          <div className="relative" ref={dropdownRef}>
            <button
              type="button"
              onClick={() => setShowKbDropdown(!showKbDropdown)}
              className={`flex h-11 items-center gap-1 rounded-md border px-3 text-sm transition-colors ${
                kb
                  ? "border-accent/40 bg-accent/10 text-accent"
                  : "border-border bg-surface text-muted hover:bg-border/30 hover:text-text"
              }`}
              title="Attach knowledge base"
            >
              <Database size={16} />
              <ChevronDown size={14} />
            </button>

            {showKbDropdown && (
              <div className="absolute bottom-full left-0 mb-2 w-56 rounded-md border border-border bg-surface shadow-lg">
                <div className="p-2">
                  <div className="px-2 py-1.5 text-xs font-medium text-muted">
                    Attach Knowledge Base
                  </div>
                  <button
                    type="button"
                    onClick={() => handleSelectKb(null)}
                    className={`mt-1 flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors hover:bg-border/30 ${
                      !chat.kbId ? "bg-accent/10 text-accent" : "text-text"
                    }`}
                  >
                    <span className="text-muted">—</span>
                    <span>None (general chat)</span>
                  </button>
                  {knowledgeBases.length > 0 ? (
                    knowledgeBases.map((k) => (
                      <button
                        key={k.id}
                        type="button"
                        onClick={() => handleSelectKb(k.id)}
                        className={`flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors hover:bg-border/30 ${
                          chat.kbId === k.id
                            ? "bg-accent/10 text-accent"
                            : "text-text"
                        }`}
                      >
                        <Database size={14} className="text-muted" />
                        <span>{k.name}</span>
                      </button>
                    ))
                  ) : (
                    <div className="px-2 py-3 text-center text-xs text-muted">
                      No knowledge bases yet.
                      <br />
                      Create one from the sidebar.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Model selector */}
          <ModelSelector
            models={modelConfigs}
            selectedModelId={selectedModelId}
            onSelectModel={actions.selectModel}
            onAddModel={actions.addModelConfig}
            onUpdateModel={actions.updateModelConfig}
            onDeleteModel={actions.deleteModelConfig}
          />

          {/* Text input */}
          <input
            ref={inputRef}
            type="text"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={kb ? `Ask about ${kb.name}…` : "Ask a question…"}
            className="h-11 flex-1 rounded-md border border-border bg-surface px-4 text-sm text-text placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-accent/40"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleSend();
              }
            }}
          />

          <Button variant="primary" size="lg" onClick={handleSend}>
            Send
          </Button>
        </div>
      </div>
    </div>
  );
}
