import { serializeModelConfig, type ModelSettings } from "./adapters";
import {
  endpoints, type ApiPath, type Dto, type Endpoint, type JsonResponse,
  type MethodFor, type OnEvent, type RequestBody,
} from "./contracts";
import { responseValidator, validateCorrelationId, validateError, validateEvent } from "./validation";

const DEFAULT_API_URL = "http://127.0.0.1:8001";

export const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

type LocalErrorCode = "NETWORK_ERROR" | "INVALID_RESPONSE" | "STREAM_INTERRUPTED";
type ErrorOptions = {
  code: Dto<"ErrorCode"> | LocalErrorCode;
  message: string;
  retryable?: boolean;
  correlationId?: string | null;
  details?: Dto<"ValidationIssue">[];
  httpStatus?: number | null;
};

export class ApiError extends Error {
  code: ErrorOptions["code"];
  retryable: boolean;
  correlationId: string | null;
  details: Dto<"ValidationIssue">[];
  httpStatus: number | null;
  constructor({ code, message, retryable = false, correlationId = null, details = [], httpStatus = null }: ErrorOptions) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.retryable = retryable;
    this.correlationId = correlationId;
    this.details = details;
    this.httpStatus = httpStatus;
  }
}

function localError(code: LocalErrorCode, correlationId: string | null = null, httpStatus: number | null = null) {
  const messages = {
    NETWORK_ERROR: "The service could not be reached. Check your connection.",
    INVALID_RESPONSE: "The service returned an invalid response.",
    STREAM_INTERRUPTED: "The response was interrupted before it finished.",
  };
  return new ApiError({
    code, message: messages[code], correlationId, httpStatus,
    retryable: code !== "INVALID_RESPONSE",
  });
}

function responseId(res: Response) {
  const id = res.headers.get("X-Correlation-ID");
  return validateCorrelationId(id) ? id : null;
}

function fromEnvelope(payload: unknown, correlationId: string | null = null, httpStatus: number | null = null) {
  if (!validateError(payload)) return localError("INVALID_RESPONSE", correlationId, httpStatus);
  const error = payload.error;
  if ((correlationId !== null && correlationId !== error.correlation_id) ||
      (error.details != null && error.code !== "VALIDATION_ERROR")) {
    return localError("INVALID_RESPONSE", correlationId, httpStatus);
  }
  return new ApiError({
    code: error.code, message: error.message, retryable: error.retryable,
    correlationId: error.correlation_id, details: error.details ?? [], httpStatus,
  });
}

export function describeApiError(error: unknown) {
  if (!(error instanceof ApiError)) return "The request could not be completed.";
  const fields = error.details.map((issue) => `${issue.field}: ${issue.message}`);
  return [
    error.message, ...fields,
    error.retryable ? "You can try again later." : null,
    error.correlationId ? `Reference: ${error.correlationId}` : null,
  ].filter(Boolean).join("\n");
}

async function requireOk(res: Response) {
  if (res.ok) return;
  let payload: unknown;
  try {
    payload = await res.json();
  } catch {
    throw localError("INVALID_RESPONSE", responseId(res), res.status);
  }
  throw fromEnvelope(payload, responseId(res), res.status);
}

function endpointUrl<P extends ApiPath, M extends MethodFor<P>>(
  endpoint: Endpoint<P, M>, parameters: Record<string, string> = {},
) {
  const path = endpoint.path.replace(/\{([^}]+)\}/g, (_, name: string) => {
    if (!(name in parameters)) throw new Error(`Missing path parameter: ${name}`);
    return encodeURIComponent(parameters[name]);
  });
  return `${API_URL}${path}`;
}

async function requestJson<P extends ApiPath, M extends MethodFor<P>>(
  endpoint: Endpoint<P, M>, options: RequestInit = {}, parameters: Record<string, string> = {},
): Promise<JsonResponse<P, M>> {
  let res: Response;
  try {
    res = await fetch(endpointUrl(endpoint, parameters), { ...options, method: endpoint.method });
  } catch {
    throw localError("NETWORK_ERROR");
  }
  await requireOk(res);
  let payload: unknown;
  try {
    payload = await res.json();
  } catch {
    throw localError("INVALID_RESPONSE", responseId(res), res.status);
  }
  const validate = responseValidator(endpoint);
  if (!validate(payload)) throw localError("INVALID_RESPONSE", responseId(res), res.status);
  return payload;
}

/** Error events reject with ApiError; only successful execution events reach onEvent. */
async function parseSSE(res: Response, onEvent: OnEvent) {
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  const correlationId = responseId(res);
  let buffer = "";

  try {
    while (true) {
      let chunk;
      try {
        chunk = await reader.read();
      } catch {
        throw localError("STREAM_INTERRUPTED", correlationId);
      }
      buffer += decoder.decode(chunk.value, { stream: !chunk.done });
      buffer = buffer.replace(/\r\n/g, "\n");
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      for (const eventBlock of events) {
        const lines = eventBlock.split("\n");
        const eventType = lines.find((line) => line.startsWith("event:"))?.slice(6).trim();
        const data = lines.filter((line) => line.startsWith("data:"))
          .map((line) => line.slice(5).replace(/^ /, "")).join("\n");
        if (!data && !eventType) continue; // Heartbeat/comment frame.
        let eventData: unknown;
        try {
          eventData = JSON.parse(data);
        } catch {
          throw localError("INVALID_RESPONSE", correlationId);
        }
        const event: unknown = { type: eventType, data: eventData };
        if (!validateEvent(event)) throw localError("INVALID_RESPONSE", correlationId);
        if (event.type === "error") throw fromEnvelope(event.data, correlationId);
        onEvent(event);
        if (event.type === "complete") return;
      }
      if (chunk.done) throw localError("STREAM_INTERRUPTED", correlationId);
    }
  } finally {
    // A tee'd response can leave cancellation pending until its other reader
    // closes. Terminal delivery must not wait for transport cleanup.
    void reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

async function requestStream<P extends ApiPath, M extends MethodFor<P>>(
  endpoint: Endpoint<P, M>, requestBody: RequestBody<P, M>,
  fallback: () => Promise<Dto<"ChatResponse"> | Dto<"QueryResponse">>, onEvent: OnEvent,
  parameters: Record<string, string> = {},
) {
  let res;
  try {
    res = await fetch(endpointUrl(endpoint, parameters), {
      method: endpoint.method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
  } catch {
    // Retain compatibility fallback only before a response is consumed.
    return completeFallback(await fallback(), onEvent);
  }
  await requireOk(res);
  if (!res.body) return completeFallback(await fallback(), onEvent);
  if (!res.headers.get("Content-Type")?.startsWith("text/event-stream")) {
    throw localError("INVALID_RESPONSE", responseId(res), res.status);
  }
  await parseSSE(res, onEvent);
}

function completeFallback(result: Dto<"ChatResponse"> | Dto<"QueryResponse">, onEvent: OnEvent) {
  onEvent({ type: "step", data: { type: "generating", title: "Generating response", description: "Processing...", details: {} } });
  if ("sources" in result && result.sources.length) onEvent({ type: "sources", data: { sources: result.sources } });
  onEvent({ type: "complete", data: { answer: result.answer } });
}

export async function listKnowledgeBases() {
  return requestJson(endpoints.listKnowledgeBases);
}

export async function getModelConfig() {
  return requestJson(endpoints.modelConfig);
}

export type CreateKnowledgeBaseParams = { name: string; embeddingModel?: string; files: File[] };
export async function createKnowledgeBase({ name, embeddingModel, files }: CreateKnowledgeBaseParams) {
  const body: RequestBody<"/api/kb", "post"> = {
    name, embedding_model: embeddingModel || undefined, files,
  };
  const form = new FormData();
  form.append("name", body.name);
  if (body.embedding_model) form.append("embedding_model", body.embedding_model);
  for (const file of body.files) form.append("files", file);
  return requestJson(endpoints.createKnowledgeBase, { body: form });
}

type QueryParams = { kbId: string; question: string; modelConfig?: ModelSettings | null };
type ChatParams = { messages: Dto<"ChatMessage">[]; modelConfig?: ModelSettings | null };

function queryBody({ question, modelConfig }: QueryParams): RequestBody<"/api/kb/{kb_id}/query", "post"> {
  return { question, model_config_override: serializeModelConfig(modelConfig) };
}

function chatBody({ messages, modelConfig }: ChatParams): RequestBody<"/api/chat", "post"> {
  return { messages, model_config_override: serializeModelConfig(modelConfig) };
}

function jsonOptions(body: unknown): RequestInit {
  return { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export async function queryKnowledgeBase(params: QueryParams) {
  return requestJson(endpoints.query, jsonOptions(queryBody(params)), { kb_id: params.kbId });
}

export async function chatWithLlm(params: ChatParams) {
  return requestJson(endpoints.chat, jsonOptions(chatBody(params)));
}

/** Errors reject with ApiError. Compatibility fallback only precedes stream consumption. */
export async function queryKnowledgeBaseStream({ onEvent, ...params }: QueryParams & { onEvent: OnEvent }) {
  const body: RequestBody<"/api/kb/{kb_id}/query/stream", "post"> = queryBody(params);
  await requestStream(endpoints.queryStream, body,
    () => queryKnowledgeBase(params), onEvent, { kb_id: params.kbId });
}

export async function chatWithLlmStream({ onEvent, ...params }: ChatParams & { onEvent: OnEvent }) {
  const body: RequestBody<"/api/chat/stream", "post"> = chatBody(params);
  await requestStream(endpoints.chatStream, body, () => chatWithLlm(params), onEvent);
}
