import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ApiError, describeApiError } from "../api/client";
import { chatRequest, createChat as apiCreateChat, followRun, getChat, getKnowledge, getRun, json, listChats, listKnowledge,
  regenerateReply, selectReplyVersion, startRun, updateChat, type AnswerVersion, type ChatEvent, type ChatRun, type ChatRunRequest, type ChatSession, type Citation, type ChatKnowledgeBase } from "../api/chat";
import type { CreateKnowledgeBaseParams } from "../api/client";

type Message = { id: string; role: string; content: string; sources: Citation[]; runId?: string | null; answerStatus?: string;
  status: string; isStreaming?: boolean; events: ChatEvent[]; run?: ChatRun; versions?: AnswerVersion[];
  pendingRunId?: string | null; canonicalRunId?: string | null; previous?: Message; notice?: string;
  lastAttemptRunId?: string; versionBusy?: boolean; errorReference?: string; request?: ChatRunRequest };
type Chat = { id: string; title: string; kbId: string | null; updatedAt: string; messages: Message[]; activeRunId: string | null; summaryStatus: string; hydrated: boolean };
type Model = { id: string; name: string; demo?: boolean };
const Context = createContext<ReturnType<typeof useAppStateValue> | null>(null);

function adaptSession(session: ChatSession): Chat {
  return { id: session.id, title: session.title || "New chat", kbId: session.kb_ids?.[0] || null,
    updatedAt: session.updated_at, activeRunId: session.active_run_id || null, summaryStatus: session.summary_status || "idle", hydrated: true,
    messages: (session.messages || []).map(m => ({ id: m.id, role: m.role, content: m.content, sources: m.sources || [],
      status: m.status || "completed", answerStatus: m.answer_status, runId: m.run_id, canonicalRunId: m.run_id,
      pendingRunId: m.pending_run_id, versions: m.versions || [], events: [],
      ...((m.versions || []).slice(-1)[0]?.status === "failed" && m.status === "completed" ? {
        notice: "Regeneration failed. Your previous answer is still available.", lastAttemptRunId: (m.versions || []).slice(-1)[0]?.run_id,
      } : (m.versions || []).slice(-1)[0]?.status === "cancelled" && m.status === "completed" ? {
        notice: "Regeneration cancelled. Your previous answer is still available.", lastAttemptRunId: (m.versions || []).slice(-1)[0]?.run_id,
      } : {}) })) };
}
function adaptKnowledge(kb: ChatKnowledgeBase) {
  const documents = (kb.documents || []).map(d => ({ id: d.id, name: d.title, type: d.content_type, size: d.size,
    status: d.status === "ready" ? "Indexed" : d.status, uploadedAt: d.created_at, updatedAt: d.updated_at || d.created_at,
    version: d.version, canDelete: d.can_delete ?? false }));
  return { id: kb.id, name: kb.name, canDelete: kb.can_delete ?? false, embeddingModel: kb.embedding_model, rankingStrategy: "Automatic per question",
    chunkingStrategy: "Token (180/30)", createdAt: kb.created_at || "", lastModified: kb.created_at || "",
    fileCount: documents.length, totalSize: documents.reduce((sum, d) => sum+d.size, 0), documents };
}
function errorText(error: unknown) {
  return error instanceof ApiError ? describeApiError(error) : "The service could not be reached. Check the backend connection and retry.";
}

function reconcileSources(message: Message, docs: Map<string, number>): Message {
  const previous = message.previous ? reconcileSources(message.previous, docs) : undefined;
  if (!message.sources.some(source => source.kind !== "tool" && source.document_id && docs.get(source.document_id) !== source.version)) {
    return previous !== message.previous ? { ...message, previous } : message;
  }
  return { ...message, previous, content: "This answer used a source that is no longer available.", status: "source_unavailable",
    sources: message.sources.map(source => source.kind !== "tool" && source.document_id && docs.get(source.document_id) !== source.version
      ? { ...source, available: false, excerpt: "", title: "Source unavailable" } : source) };
}

function useAppStateValue() {
  const [knowledgeBases, setKnowledgeBases] = useState<ReturnType<typeof adaptKnowledge>[]>([]);
  const [chatHistory, setChatHistory] = useState<Chat[]>([]);
  const [modelConfigs, setModels] = useState<Model[]>([]);
  const [selectedModelId, selectModel] = useState("default");
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState("");
  const [knowledgeLoading, setKnowledgeLoading] = useState(true);
  const [knowledgeFailure, setKnowledgeFailure] = useState("");
  const knowledgeEpoch = useRef(0);
  const knowledgeRequest = useRef<AbortController | null>(null);
  const [ephemeral, setEphemeral] = useState(false);
  const chats = useRef(chatHistory); chats.current = chatHistory;
  const models = useRef(selectedModelId); models.current = selectedModelId;
  const listeners = useRef(new Map<string, AbortController>());
  const sending = useRef(new Set<string>());
  const opening = useRef(new Set<string>());
  const creation = useRef<Promise<Chat> | null>(null);
  const bootstrap = useRef<Promise<void> | null>(null);

  const reconcileKnowledge = useCallback((bases: ReturnType<typeof adaptKnowledge>[]) => {
    const ids = new Set(bases.map(kb => kb.id));
    const docs = new Map(bases.flatMap(kb => kb.documents.map(doc => [doc.id, doc.version] as const)));
    setChatHistory(previous => previous.map(chat => ({ ...chat, kbId: chat.kbId && ids.has(chat.kbId) ? chat.kbId : null,
      messages: chat.messages.map(message => reconcileSources(message, docs)) })));
  }, []);
  const refreshKnowledge = useCallback(async () => {
    const epoch = ++knowledgeEpoch.current;
    knowledgeRequest.current?.abort();
    const controller = new AbortController(); knowledgeRequest.current = controller;
    setKnowledgeLoading(true);
    try {
      const kbs = await listKnowledge(controller.signal);
      if (epoch === knowledgeEpoch.current && !controller.signal.aborted) {
        const bases = kbs.map(adaptKnowledge);
        setKnowledgeBases(bases); reconcileKnowledge(bases); setKnowledgeFailure("");
      }
      return kbs;
    } catch (error) {
      if (!controller.signal.aborted && epoch === knowledgeEpoch.current) setKnowledgeFailure(errorText(error));
      throw error;
    } finally {
      if (knowledgeRequest.current === controller) { knowledgeRequest.current = null; setKnowledgeLoading(false); }
    }
  }, [reconcileKnowledge]);
  const refreshKnowledgeBase = useCallback(async (id: string, signal?: AbortSignal) => {
    const epoch = knowledgeEpoch.current;
    const base = adaptKnowledge(await getKnowledge(id, signal));
    if (!signal?.aborted && epoch === knowledgeEpoch.current) {
      setKnowledgeBases(previous => [...previous.filter(kb => kb.id !== id), base]);
    }
    return base;
  }, []);
  const refresh = useCallback(async () => {
    setLoading(true); setFailure("");
    try {
      const [sessions, settings] = await Promise.all([listChats(), chatRequest<{
        models: Model[]; ephemeral: boolean }>("/settings/public"), refreshKnowledge().catch(() => {})]);
      setChatHistory(previous => sessions.map(s => previous.find(c => c.id === s.id && c.hydrated) || { ...adaptSession(s), hydrated: false }));
      setModels(settings.models); setEphemeral(settings.ephemeral);
    } catch (error) { setFailure(errorText(error)); }
    finally { setLoading(false); }
  }, [refreshKnowledge]);
  useEffect(() => {
    bootstrap.current ??= refresh();
    // StrictMode replays effects; keep one bootstrap and one set of active subscriptions.
  }, [refresh]);

  const patchMessage = useCallback((chatId: string, runId: string, change: (m: Message) => Message) => {
    setChatHistory(previous => previous.map(chat => chat.id !== chatId ? chat : { ...chat,
      messages: chat.messages.map(m => m.role === "assistant" && m.runId === runId ? change(m) : m) }));
  }, []);
  const applyEvent = useCallback((chatId: string, event: ChatEvent) => {
    patchMessage(chatId, event.run_id, message => {
      if (message.events.some(e => e.id === event.id)) return message;
      const next = { ...message, events: [...message.events, event] };
      if (event.type === "token") next.content += event.data.token;
      if (event.type === "complete") {
        next.content = event.data.answer || ""; next.sources = event.data.sources || []; next.answerStatus = event.data.answer_status;
        next.status = "completed"; next.isStreaming = false; next.run = event.data;
        next.canonicalRunId = event.run_id; next.previous = undefined; next.notice = undefined;
        next.lastAttemptRunId = undefined; next.errorReference = undefined;
        next.versions = (next.versions || []).map(v => v.run_id === event.run_id ? { ...v, status: "completed" } : v);
      }
      if (event.type === "error" || event.type === "cancelled") {
        const versions = (next.versions || []).map(v => v.run_id === event.run_id ? { ...v, status: event.type === "cancelled" ? "cancelled" : "failed" } : v);
        if (next.previous?.status === "completed") return { ...next.previous, versions, isStreaming: false,
          notice: `${event.type === "cancelled" ? "Regeneration cancelled." : "Regeneration failed."} Your previous answer is still available.`,
          lastAttemptRunId: event.run_id, errorReference: event.data.correlation_id };
        next.content = event.data.message; next.errorReference = event.data.correlation_id; next.versions = versions;
        next.sources = []; next.status = event.type === "cancelled" ? "cancelled" : "failed"; next.isStreaming = false;
      }
      return next;
    });
  }, [patchMessage]);
  const subscribe = useCallback(async (chatId: string, runId: string) => {
    if (listeners.current.has(runId)) return;
    const controller = new AbortController(); listeners.current.set(runId, controller);
    try {
      await followRun(runId, event => applyEvent(chatId, event), controller.signal);
      const session = await getChat(chatId);
      const restored = adaptSession(session);
      sending.current.delete(chatId);
      setChatHistory(previous => previous.map(c => c.id === chatId ? { ...c, activeRunId: restored.activeRunId,
        summaryStatus: restored.summaryStatus, updatedAt: restored.updatedAt,
        messages: c.messages.map(m => {
          const fresh = restored.messages.find(item => item.id === m.id);
          return fresh && (fresh.versions || []).some(v => v.run_id === runId) ? { ...fresh,
            events: fresh.runId === m.runId ? m.events : [], run: fresh.runId === m.runId ? m.run : undefined } : m;
        }) } : c));
    }
    catch (error) {
      if (!controller.signal.aborted) patchMessage(chatId, runId, m => m.previous?.status === "completed"
        ? { ...m.previous, notice: errorText(error), lastAttemptRunId: runId, isStreaming: false, status: "disconnected" }
        : { ...m, content: errorText(error), isStreaming: false, status: "disconnected" });
    } finally { listeners.current.delete(runId); sending.current.delete(chatId); }
  }, [applyEvent, patchMessage]);

  const createChat = useCallback(async ({ kbId = null }: { kbId?: string | null } = {}) => {
    try {
      const chat = adaptSession(await apiCreateChat(kbId ? [kbId] : []));
      setChatHistory(previous => [chat, ...previous.filter(c => c.id !== chat.id)]);
      return chat;
    } catch (error) { setFailure(errorText(error)); throw error; }
  }, []);
  const startChat = useCallback(() => {
    if (chats.current.length) return Promise.resolve([...chats.current].sort((a,b) => b.updatedAt.localeCompare(a.updatedAt))[0]);
    creation.current ??= createChat().finally(() => { creation.current = null; });
    return creation.current;
  }, [createChat]);
  const openChat = useCallback(async (id: string) => {
    if (opening.current.has(id)) return;
    opening.current.add(id);
    try {
      const chat = adaptSession(await getChat(id));
      if (chat.activeRunId) {
        const run = await getRun(chat.activeRunId);
        const target = chat.messages.find(m => m.role === "assistant" &&
          (m.id === run.assistant_message_id || m.pendingRunId === run.id || m.runId === run.id));
        if (target) Object.assign(target, { previous: target.status === "completed" ? { ...target } : undefined,
          content: "", sources: [], runId: run.id, status: "running", isStreaming: true });
        else chat.messages.push({ id: run.assistant_message_id || `pending-${run.id}`, role: "assistant", content: "", sources: [], events: [],
          runId: run.id, status: "running", isStreaming: true });
      }
      if (sending.current.has(id) && !chat.activeRunId) return;
      setChatHistory(previous => [...previous.filter(c => c.id !== id), chat]);
      if (chat.activeRunId) void subscribe(id, chat.activeRunId);
    } catch (error) { setFailure(errorText(error)); }
    finally { opening.current.delete(id); }
  }, [subscribe]);

  const sendMessage = useCallback(async (chatId: string, prompt: string, mode: "auto" | "agentic" = "auto",
    retry?: { assistantId: string; request: ChatRunRequest }) => {
    if (!prompt.trim() || sending.current.has(chatId)) return;
    const chat = chats.current.find(c => c.id === chatId);
    if (!chat || chat.activeRunId) return;
    sending.current.add(chatId); setFailure("");
    const clientId = retry?.request.client_message_id || crypto.randomUUID();
    const userMessage: Message = { id: clientId, role: "user", content: prompt.trim(), sources: [], events: [], status: "completed" };
    const assistantId = retry?.assistantId || crypto.randomUUID();
    const request: ChatRunRequest = retry?.request || { question: prompt.trim(), session_id: chatId,
      kb_ids: chat.kbId ? [chat.kbId] : [], mode, model_id: models.current, client_message_id: clientId };
    setChatHistory(previous => previous.map(c => c.id !== chatId ? c : { ...c,
      title: c.title === "New chat" ? prompt.slice(0, 32) : c.title,
      messages: retry ? c.messages.map(m => m.id === assistantId ? { ...m, content: "", sources: [], events: [],
        status: "pending", isStreaming: true, notice: undefined } : m) :
        [...c.messages, userMessage, { id: assistantId, role: "assistant", content: "", sources: [],
          events: [], status: "pending", isStreaming: true, request }] }));
    try {
      const accepted = await startRun(request);
      setChatHistory(previous => previous.map(c => c.id !== chatId ? c : { ...c, activeRunId: accepted.run_id,
        messages: c.messages.map(m => m.id === assistantId || m.id === clientId ? { ...m,
          id: m.id === assistantId ? accepted.assistant_message_id || m.id : accepted.user_message_id || m.id,
          runId: accepted.run_id, canonicalRunId: accepted.run_id,
          versions: m.role === "assistant" ? [{ run_id: accepted.run_id, status: "pending", created_at: new Date().toISOString() }] : [] } : m) }));
      await subscribe(chatId, accepted.run_id);
    } catch (error) {
      setChatHistory(previous => previous.map(c => c.id !== chatId ? c : { ...c, messages: c.messages.map(m => m.id !== assistantId ? m : {
        ...m, content: errorText(error), status: "failed", isStreaming: false }) }));
    } finally { sending.current.delete(chatId); }
  }, [subscribe]);

  const regenerateResponse = useCallback(async (chatId: string, messageId: string) => {
    const chat = chats.current.find(c => c.id === chatId);
    const message = chat?.messages.find(m => m.id === messageId);
    if (message && !message.runId && message.request) {
      await sendMessage(chatId, message.request.question, message.request.mode === "agentic" ? "agentic" : "auto", { assistantId: messageId, request: message.request });
      return;
    }
    if (!chat || !message?.runId || chat.activeRunId || sending.current.has(chatId)) return;
    sending.current.add(chatId);
    const prior = { ...message, previous: undefined };
    setChatHistory(previous => previous.map(c => c.id !== chatId ? c : { ...c,
      messages: c.messages.map(m => m.id !== messageId ? m : { ...m, previous: prior, content: "", sources: [],
        events: [], run: undefined, isStreaming: true, status: "pending", notice: undefined }) }));
    try {
      const accepted = await regenerateReply(chatId, messageId, message.runId, crypto.randomUUID());
      setChatHistory(previous => previous.map(c => c.id !== chatId ? c : { ...c, activeRunId: accepted.run_id,
        messages: c.messages.map(m => m.id !== messageId ? m : { ...m, runId: accepted.run_id,
          versions: [...(m.versions || []), { run_id: accepted.run_id, status: "pending", created_at: new Date().toISOString() }] }) }));
      await subscribe(chatId, accepted.run_id);
    } catch (error) {
      setChatHistory(previous => previous.map(c => c.id !== chatId ? c : { ...c,
        messages: c.messages.map(m => m.id !== messageId ? m : { ...prior, notice: errorText(error) }) }));
      sending.current.delete(chatId);
      if (error instanceof ApiError && error.httpStatus === 409) await openChat(chatId);
    } finally { sending.current.delete(chatId); }
  }, [subscribe, openChat, sendMessage]);

  const selectAnswerVersion = useCallback(async (chatId: string, messageId: string, runId: string) => {
    const chat = chats.current.find(c => c.id === chatId);
    const message = chat?.messages.find(m => m.id === messageId);
    if (!chat || !message?.runId || chat.activeRunId || sending.current.has(chatId)) return;
    const latest = chat.messages.slice(-1)[0]?.id === messageId;
    sending.current.add(chatId);
    setChatHistory(previous => previous.map(c => c.id !== chatId ? c : { ...c,
      messages: c.messages.map(m => m.id !== messageId ? m : { ...m, versionBusy: true }) }));
    try {
      if (latest) {
        const selected = await selectReplyVersion(chatId, messageId, runId, message.runId);
        setChatHistory(previous => previous.map(c => c.id !== chatId ? c : { ...c,
          messages: c.messages.map(m => m.id !== messageId ? m : { ...m, content: selected.content, sources: selected.sources || [],
            runId: selected.run_id, canonicalRunId: selected.run_id, versions: selected.versions,
            status: selected.status || "completed", answerStatus: selected.answer_status, events: [], run: undefined, notice: undefined }) }));
      } else {
        const run = await getRun(runId);
        setChatHistory(previous => previous.map(c => c.id !== chatId ? c : { ...c,
          messages: c.messages.map(m => m.id !== messageId ? m : { ...m, content: run.answer || "", sources: run.sources || [],
            runId, status: run.status, answerStatus: run.answer_status, run, events: [],
            notice: runId !== m.canonicalRunId ? "Viewing another version. Existing follow-ups keep their original context." : undefined }) }));
      }
    } catch (error) {
      setFailure(errorText(error));
      sending.current.delete(chatId);
      if (error instanceof ApiError && error.httpStatus === 409) await openChat(chatId);
    } finally {
      sending.current.delete(chatId);
      setChatHistory(previous => previous.map(c => c.id !== chatId ? c : { ...c,
        messages: c.messages.map(m => m.id !== messageId ? m : { ...m, versionBusy: false }) }));
    }
  }, [openChat]);

  const stopResponse = useCallback(async (chatId: string) => {
    const runId = chats.current.find(c => c.id === chatId)?.activeRunId;
    if (!runId) return;
    try {
      await chatRequest(`/runs/${encodeURIComponent(runId)}/cancel`, json("POST", {}));
      listeners.current.get(runId)?.abort();
      sending.current.delete(chatId);
      await openChat(chatId);
    } catch (error) { setFailure(errorText(error)); }
  }, [openChat]);
  const setChatKnowledgeBase = useCallback(async (id: string, kbId: string | null) => {
    setFailure("");
    try {
      const updated = await updateChat(id, kbId ? [kbId] : []);
      setChatHistory(previous => previous.map(c => c.id === id ? { ...c, kbId: updated.kb_ids?.[0] || null } : c));
      return true;
    } catch (error) { setFailure(errorText(error)); return false; }
  }, []);
  const deleteChat = useCallback(async (id: string) => {
    try {
      await chatRequest(`/sessions/${encodeURIComponent(id)}`, { method: "DELETE" });
      setChatHistory(previous => previous.filter(c => c.id !== id));
    } catch (error) { setFailure(errorText(error)); }
  }, []);
  const uploadDocuments = useCallback(async (id: string, files: File[]) => {
    const form = new FormData(); for (const file of files) form.append("files", file, file.name);
    try {
      await chatRequest(`/kb/${encodeURIComponent(id)}/documents`, { method: "POST", body: form });
    } catch (error) {
      await refreshKnowledge().catch(() => {});
      throw error;
    }
    await refreshKnowledge().catch(() => {});
  }, [refreshKnowledge]);
  const createKnowledgeBase = useCallback(async (payload: CreateKnowledgeBaseParams & { onCreated?: (id: string) => void }) => {
    const created = await chatRequest<ChatKnowledgeBase>("/kb", json("POST", { name: payload.name }));
    ++knowledgeEpoch.current; knowledgeRequest.current?.abort();
    setKnowledgeBases(previous => [...previous, adaptKnowledge(created)]);
    payload.onCreated?.(created.id);
    if (payload.files?.length) await uploadDocuments(created.id, payload.files);
    return adaptKnowledge(created);
  }, [uploadDocuments]);
  const deleteKnowledgeBase = useCallback(async (id: string) => {
    await chatRequest(`/kb/${encodeURIComponent(id)}`, { method: "DELETE" });
    ++knowledgeEpoch.current; knowledgeRequest.current?.abort();
    setKnowledgeBases(previous => previous.filter(k => k.id !== id));
    setChatHistory(previous => previous.map(chat => chat.kbId === id ? { ...chat, kbId: null } : chat));
    await refreshKnowledge().catch(() => {});
  }, [refreshKnowledge]);
  const deleteDocument = useCallback(async (kbId: string, id: string) => {
    await chatRequest(`/documents/${encodeURIComponent(id)}`, { method: "DELETE" });
    ++knowledgeEpoch.current; knowledgeRequest.current?.abort();
    setKnowledgeBases(previous => previous.map(kb => kb.id === kbId ? { ...kb, documents: kb.documents.filter(doc => doc.id !== id) } : kb));
    await refreshKnowledge().catch(() => {});
  }, [refreshKnowledge]);
  const processing = knowledgeBases.some(k => k.documents.some(d => ["processing", "queued", "running"].includes(d.status)));
  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(() => {
      if (!document.hidden && !knowledgeRequest.current) void refreshKnowledge().catch(() => {});
    }, 1000);
    return () => clearInterval(timer);
  }, [processing, refreshKnowledge]);
  useEffect(() => {
    const focus = () => { void refreshKnowledge().catch(() => {}); };
    window.addEventListener("focus", focus);
    return () => window.removeEventListener("focus", focus);
  }, [refreshKnowledge]);
  useEffect(() => {
    const ids = chatHistory.filter(c => ["queued", "running"].includes(c.summaryStatus)).map(c => c.id);
    if (!ids.length) return;
    const timer = setInterval(() => { for (const id of ids) void getChat(id).then(session => {
      setChatHistory(previous => previous.map(c => c.id === id ? { ...c, summaryStatus: session.summary_status || "idle", updatedAt: session.updated_at } : c));
    }).catch(() => {}); }, 1000);
    return () => clearInterval(timer);
  }, [chatHistory]);
  const actions = useMemo(() => ({ createChat, startChat, openChat, sendMessage, stopResponse, regenerateResponse, selectAnswerVersion, setChatKnowledgeBase,
    deleteChat, createKnowledgeBase, deleteKnowledgeBase, deleteDocument, uploadDocuments, refresh, refreshKnowledge, refreshKnowledgeBase, selectModel,
    computeKbStats: (kb: ReturnType<typeof adaptKnowledge>) => ({ ...kb, fileCount: kb.documents.length,
      totalSize: kb.documents.reduce((sum, d) => sum+d.size, 0) }) }),
    [createChat, startChat, openChat, sendMessage, stopResponse, regenerateResponse, selectAnswerVersion, setChatKnowledgeBase, deleteChat,
      createKnowledgeBase, deleteKnowledgeBase, deleteDocument, uploadDocuments, refresh, refreshKnowledge, refreshKnowledgeBase]);
  return { knowledgeBases, chatHistory, modelConfigs, selectedModelId, loading, failure, knowledgeLoading, knowledgeFailure, ephemeral, actions };
}
export function AppStateProvider({ children }: { children: ReactNode }) {
  return <Context.Provider value={useAppStateValue()}>{children}</Context.Provider>;
}
export function useAppState() {
  const value = useContext(Context);
  if (!value) throw new Error("useAppState must be used inside AppStateProvider");
  return value;
}
