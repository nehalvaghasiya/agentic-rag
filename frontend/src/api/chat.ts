import Ajv2020 from "ajv/dist/2020.js";
import specification from "../../../contracts/openapi.json";
import type { components } from "./generated/chat";
import { ApiError } from "./client";

type Schema = components["schemas"];
export type ChatSession = Schema["SessionResponse"];
export type ChatEvent = Schema["ExecutionEnvelope"];
export type ChatRun = Schema["RunResponse"];
export type Citation = Schema["Citation"];
export type ChatKnowledgeBase = Schema["KnowledgeBaseResponse"];
export type ChatRunRequest = Schema["RunRequest"];
export type ChatMessage = Schema["ChatMessage"];
export type AnswerVersion = Schema["AnswerVersion"];
export type DocumentPreview = Schema["DocumentPreviewResponse"];
export const CHAT_API_URL = import.meta.env.VITE_API_URL || globalThis.location?.origin || "";
const ajv = new Ajv2020({ strict: false, allErrors: true, validateFormats: false });
ajv.addSchema({ $id: "chat-api", components: specification.components });

function validate<T>(schema: keyof Schema, value: unknown): T {
  const validator = ajv.getSchema(`chat-api#/components/schemas/${schema}`);
  if (!validator?.(value)) throw new ApiError({ code: "INVALID_RESPONSE", message: "The server returned an invalid chat response.", retryable: false });
  return value as T;
}

async function requestResponse(path: string, init: RequestInit = {}): Promise<Response> {
  const response = await fetch(`${CHAT_API_URL}/api/v2${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError({ code: body.error?.code || "REQUEST_FAILED", message: body.error?.message || `Request failed (${response.status}).`,
      retryable: body.error?.retryable ?? false, correlationId: body.error?.correlation_id, httpStatus: response.status });
  }
  return response;
}

export async function chatRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await requestResponse(path, init);
  return response.status === 204 ? undefined as T : await response.json() as T;
}

export function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export async function listChats() {
  const raw = await chatRequest<unknown[]>("/sessions");
  return raw.map(value => validate<ChatSession>("SessionResponse", value));
}
export async function createChat(kbIds: string[] = []) {
  return validate<ChatSession>("SessionResponse", await chatRequest("/sessions", json("POST", { kb_ids: kbIds })));
}
export async function getChat(id: string) {
  return validate<ChatSession>("SessionResponse", await chatRequest(`/sessions/${encodeURIComponent(id)}`));
}
export async function updateChat(id: string, kbIds: string[]) {
  return validate<ChatSession>("SessionResponse", await chatRequest(`/sessions/${encodeURIComponent(id)}`, json("PATCH", { kb_ids: kbIds })));
}
export async function listKnowledge(signal?: AbortSignal) {
  const raw = await chatRequest<unknown[]>("/kb", { signal });
  return raw.map(value => validate<ChatKnowledgeBase>("KnowledgeBaseResponse", value));
}
export async function getKnowledge(id: string, signal?: AbortSignal) {
  return validate<ChatKnowledgeBase>("KnowledgeBaseResponse", await chatRequest(`/kb/${encodeURIComponent(id)}`, { signal }));
}
export async function getDocumentPreview(id: string, version: number, offset = 0, signal?: AbortSignal) {
  return validate<DocumentPreview>("DocumentPreviewResponse", await chatRequest(
    `/documents/${encodeURIComponent(id)}/preview?version=${version}&offset=${offset}`, { signal }));
}
export async function getDocumentFile(id: string, version: number, signal?: AbortSignal) {
  const response = await requestResponse(`/documents/${encodeURIComponent(id)}/download?version=${version}`, { signal });
  return response.blob();
}
export async function startRun(payload: ChatRunRequest) {
  // A network retry reuses the exact message ID. Never replay a generation after consuming SSE.
  for (let attempt = 0; ; attempt++) {
    try {
      return validate<Schema["RunAccepted"]>("RunAccepted", await chatRequest("/runs", json("POST", payload)));
    } catch (error) {
      if (error instanceof ApiError || attempt >= 1) throw error;
    }
  }
}
export async function getRun(id: string, signal?: AbortSignal) {
  return validate<ChatRun>("RunResponse", await chatRequest(`/runs/${encodeURIComponent(id)}`, { signal }));
}
export async function getActivity(id: string, signal?: AbortSignal) {
  const raw = await chatRequest<unknown[]>(`/runs/${encodeURIComponent(id)}/activity`, { signal });
  return raw.map(value => validate<ChatEvent>("ExecutionEnvelope", value));
}

export async function regenerateReply(chatId: string, messageId: string, expectedRunId: string, requestId: string) {
  const path = `/sessions/${encodeURIComponent(chatId)}/messages/${encodeURIComponent(messageId)}/regenerate`;
  const payload = { expected_run_id: expectedRunId, client_request_id: requestId };
  for (let attempt = 0; ; attempt++) {
    try { return validate<Schema["RunAccepted"]>("RunAccepted", await chatRequest(path, json("POST", payload))); }
    catch (error) { if (error instanceof ApiError || attempt >= 1) throw error; }
  }
}

export async function selectReplyVersion(chatId: string, messageId: string, runId: string, expectedRunId: string) {
  return validate<ChatMessage>("ChatMessage", await chatRequest(
    `/sessions/${encodeURIComponent(chatId)}/messages/${encodeURIComponent(messageId)}/version`,
    json("PATCH", { run_id: runId, expected_run_id: expectedRunId })));
}

export async function followRun(id: string, onEvent: (event: ChatEvent) => void, signal: AbortSignal, startCursor = 0) {
  let cursor = startCursor;
  for (let reconnect = 0; reconnect < 5; reconnect++) {
    try {
      const response = await fetch(`${CHAT_API_URL}/api/v2/runs/${encodeURIComponent(id)}/events`, {
        signal, headers: cursor ? { "Last-Event-ID": String(cursor) } : {},
      });
      if (!response.ok || !response.body || !response.headers.get("Content-Type")?.startsWith("text/event-stream")) {
        throw new Error("Unable to subscribe to this response.");
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      try {
        while (true) {
          const { value, done } = await reader.read();
          buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
          if (buffer.length > 256000) throw new ApiError({ code: "INVALID_RESPONSE", message: "Chat event exceeded the size limit." });
          const blocks = buffer.split("\n\n");
          buffer = blocks.pop() || "";
          for (const block of blocks) {
            const raw = block.split("\n").filter(line => line.startsWith("data:")).map(line => line.slice(5).trimStart()).join("\n");
            if (!raw) continue;
            let decoded: unknown;
            try { decoded = JSON.parse(raw); }
            catch { throw new ApiError({ code: "INVALID_RESPONSE", message: "The server sent malformed chat activity." }); }
            const event = validate<ChatEvent>("ExecutionEnvelope", decoded);
            if (event.run_id !== id) throw new ApiError({ code: "INVALID_RESPONSE", message: "Chat event belongs to a different response." });
            if (event.id <= cursor) continue;
            cursor = event.id;
            onEvent(event);
            if (["complete", "error", "cancelled"].includes(event.type)) return;
          }
          if (done) break;
        }
      } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
    } catch (error) {
      if (signal.aborted || error instanceof ApiError) throw error;
    }
    // Recover from a lost terminal frame using the authoritative snapshot.
    const run = await getRun(id);
    if (["completed", "failed", "cancelled"].includes(run.status)) {
      const activity = await getActivity(id);
      for (const event of activity) if (event.id > cursor) { cursor = event.id; onEvent(event); }
      return;
    }
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => { signal.removeEventListener("abort", abort); resolve(); }, 300 * 2**reconnect);
      function abort() { clearTimeout(timer); reject(new DOMException("Aborted", "AbortError")); }
      signal.addEventListener("abort", abort, { once: true });
    });
  }
  throw new Error("Connection interrupted. Reopen this chat to reconnect to its response.");
}
