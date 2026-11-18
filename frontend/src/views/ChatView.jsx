import { useEffect, useRef, useState } from "react";
import { ArrowDown, Info } from "lucide-react";
import { useParams } from "react-router-dom";
import { ChatBubble } from "../components/features/chat/ChatBubble";
import { ChatComposer } from "../components/features/chat/ChatComposer";
import { ResponsePanel } from "../components/features/chat/ResponsePanel";
import { ActionMenu } from "../components/ui/ActionMenu";
import { useAppState } from "../state/AppStateContext";

export function ChatView() {
  const { chatId } = useParams();
  const { chatHistory, knowledgeBases, modelConfigs, selectedModelId, actions, loading, knowledgeLoading, knowledgeFailure } = useAppState();
  const [value, setValue] = useState("");
  const [deep, setDeep] = useState(false);
  const [panel, setPanel] = useState(null);
  const [docked, setDocked] = useState(false);
  const [showJump, setShowJump] = useState(false);
  const frame = useRef(null);
  const transcript = useRef(null);
  const following = useRef(true);
  const chat = chatHistory.find(c => c.id === chatId);
  const generating = Boolean(chat?.activeRunId || chat?.messages.some(m => m.isStreaming));
  const busy = generating || chat?.messages.some(m => m.versionBusy);
  useEffect(() => { if (!loading) void actions.openChat(chatId); }, [chatId, loading, actions]);
  useEffect(() => { setPanel(null); following.current = true; setShowJump(false); }, [chatId]);
  useEffect(() => {
    if (!frame.current) return;
    const update = () => setDocked(frame.current.getBoundingClientRect().width >= 960);
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(update) : null;
    observer?.observe(frame.current); window.addEventListener("resize", update); update();
    return () => { observer?.disconnect(); window.removeEventListener("resize", update); };
  }, [chat?.id]);
  useEffect(() => {
    const element = transcript.current;
    if (element && following.current) element.scrollTop = element.scrollHeight;
  }, [chat?.messages]);
  if (!chat) return <div className="p-8 text-sm text-muted">{loading ? "Loading conversation…" : "Opening conversation…"}</div>;
  const submit = event => {
    event.preventDefault();
    if (!value.trim() || busy) return;
    following.current = true; setShowJump(false);
    void actions.sendMessage(chat.id, value, deep ? "agentic" : "auto"); setValue("");
  };
  const selectedMessage = panel && chat.messages.find(m => m.id === panel.messageId);
  const currentPanel = panel && { ...panel, runId: panel.attemptRunId || selectedMessage?.runId };
  return <div ref={frame} className="flex h-full min-w-0 overflow-hidden">
    <div className="flex min-w-0 flex-1 flex-col">
      <header className="flex min-h-16 shrink-0 items-center justify-between gap-3 border-b border-border py-2 pl-16 pr-4 lg:pl-6">
        <h1 className="min-w-0 truncate text-sm font-semibold text-text" title={chat.title}>{chat.title}</h1>
        <ActionMenu label="Conversation options" items={[{ label: "Conversation details", icon: Info,
          onSelect: () => setPanel({ section: "conversation" }) }]} />
      </header>
      <div className="relative flex min-h-0 flex-1">
        <div ref={transcript} className="min-w-0 flex-1 overflow-y-auto overscroll-contain px-4 py-6 sm:px-6"
          aria-live="polite" aria-relevant="additions text" aria-label="Conversation" onScroll={event => {
            const element = event.currentTarget;
            following.current = element.scrollHeight - element.scrollTop - element.clientHeight < 96;
            setShowJump(!following.current);
          }}>
          {!chat.hydrated && <p className="text-sm text-muted">Loading conversation…</p>}
          {chat.hydrated && chat.messages.length === 0 && <div className="mx-auto max-w-xl py-12 text-center text-muted">
            <h2 className="mb-3 text-2xl font-semibold text-text">What would you like to know?</h2>
            <p>Ask a question or attach a knowledge base to get started.</p>
          </div>}
          <div className="mx-auto max-w-[800px] space-y-6 pb-10">{chat.messages.map((message, index) => <ChatBubble key={message.id} {...message}
            isLatest={index === chat.messages.length - 1} chatBusy={busy}
            onRegenerate={() => void actions.regenerateResponse(chat.id, message.id)}
            onReconnect={() => void actions.openChat(chat.id)}
            onVersion={runId => {
              if (panel?.messageId === message.id) setPanel(previous => ({ ...previous, sourceIds: [], attemptRunId: undefined }));
              void actions.selectAnswerVersion(chat.id, message.id, runId);
            }}
            onOpen={(section, sourceIds = [], attemptRunId) => setPanel({ section, messageId: message.id, sourceIds, attemptRunId })} />)}</div>
        </div>
        {showJump && <button type="button" aria-label="Jump to latest" title="Jump to latest" className="response-icon absolute bottom-4 left-1/2 -translate-x-1/2 border border-border bg-surface shadow-md"
          onClick={() => { following.current = true; transcript.current.scrollTop = transcript.current.scrollHeight; setShowJump(false); }}><ArrowDown size={18} /></button>}
      </div>
      <div className="shrink-0 px-4 pb-4 pt-2 sm:px-6 sm:pb-5">
        <ChatComposer value={value} onValueChange={setValue} onSubmit={submit} onStop={() => void actions.stopResponse(chat.id)}
          knowledgeBases={knowledgeBases} kbId={chat.kbId} onKnowledgeBaseChange={id => actions.setChatKnowledgeBase(chat.id, id)}
          knowledgeLoading={knowledgeLoading} knowledgeFailure={knowledgeFailure} onRetryKnowledge={() => void actions.refreshKnowledge().catch(() => {})}
          modelConfigs={modelConfigs} selectedModelId={selectedModelId} onModelChange={actions.selectModel}
          deep={deep} onDeepChange={setDeep} hydrated={chat.hydrated} busy={busy} generating={generating}
          canStop={Boolean(chat.activeRunId)} versionBusy={chat.messages.some(message => message.versionBusy)} />
      </div>
    </div>
    {currentPanel && <ResponsePanel key={`${chat.id}-${currentPanel.section}-${currentPanel.runId || "conversation"}`}
      panel={currentPanel} message={selectedMessage} chat={chat} docked={docked} onClose={() => setPanel(null)} />}
  </div>;
}
