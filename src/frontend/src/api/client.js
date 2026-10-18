const DEFAULT_API_URL = "http://127.0.0.1:8001";

export const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const VALIDATION_CODES = new Set(["required", "invalid_type", "invalid_json", "invalid_value"]);

export class ApiError extends Error {
  constructor({ code, message, retryable = false, correlationId = null, details = [], httpStatus = null }) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.retryable = retryable;
    this.correlationId = correlationId;
    this.details = details;
    this.httpStatus = httpStatus;
  }
}

function localError(code, correlationId = null, httpStatus = null) {
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

function responseId(res) {
  const id = res.headers.get("X-Correlation-ID");
  return typeof id === "string" && UUID.test(id) ? id : null;
}

function fromEnvelope(payload, correlationId = null, httpStatus = null) {
  const error = payload?.error;
  const details = error?.details;
  if (!error || typeof error.code !== "string" || !/^[A-Z_]{1,64}$/.test(error.code) ||
      typeof error.message !== "string" || !error.message || error.message.length > 512 ||
      typeof error.retryable !== "boolean" || typeof error.correlation_id !== "string" ||
      !UUID.test(error.correlation_id) ||
      (correlationId !== null && correlationId !== error.correlation_id) ||
      (details !== undefined && (error.code !== "VALIDATION_ERROR" || !Array.isArray(details) ||
        details.length > 20 || details.some((issue) =>
          !issue || typeof issue.field !== "string" || issue.field.length > 256 ||
          !VALIDATION_CODES.has(issue.code) || typeof issue.message !== "string" ||
          !issue.message || issue.message.length > 256)))) {
    return localError("INVALID_RESPONSE", correlationId, httpStatus);
  }
  return new ApiError({
    code: error.code, message: error.message, retryable: error.retryable,
    correlationId: error.correlation_id, details: details || [], httpStatus,
  });
}

export function describeApiError(error) {
  if (!(error instanceof ApiError)) return "The request could not be completed.";
  const fields = error.details.map((issue) => `${issue.field}: ${issue.message}`);
  return [
    error.message, ...fields,
    error.retryable ? "You can try again later." : null,
    error.correlationId ? `Reference: ${error.correlationId}` : null,
  ].filter(Boolean).join("\n");
}

async function requireOk(res) {
  if (res.ok) return;
  let payload;
  try {
    payload = await res.json();
  } catch {
    throw localError("INVALID_RESPONSE", responseId(res), res.status);
  }
  throw fromEnvelope(payload, responseId(res), res.status);
}

async function requestJson(path, options = {}) {
  let res;
  try {
    res = await fetch(`${API_URL}${path}`, options);
  } catch {
    throw localError("NETWORK_ERROR");
  }
  await requireOk(res);
  try {
    return await res.json();
  } catch {
    throw localError("INVALID_RESPONSE", responseId(res), res.status);
  }
}

/** Error events reject with ApiError; only successful execution events reach onEvent. */
async function parseSSE(res, onEvent) {
  const reader = res.body.getReader();
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
        let eventData;
        try {
          eventData = JSON.parse(data);
        } catch {
          throw localError("INVALID_RESPONSE", correlationId);
        }
        if (eventType === "error") throw fromEnvelope(eventData, correlationId);
        if (!eventType || !eventData || typeof eventData !== "object" ||
            (eventType === "complete" && typeof eventData.answer !== "string") ||
            (eventType === "token" && typeof eventData.token !== "string")) {
          throw localError("INVALID_RESPONSE", correlationId);
        }
        onEvent({ type: eventType, data: eventData });
        if (eventType === "complete") return;
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

async function requestStream(path, requestBody, fallback, onEvent) {
  let res;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: "POST",
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

function completeFallback(result, onEvent) {
  onEvent({ type: "step", data: { type: "generating", title: "Generating response", description: "Processing..." } });
  if (result.sources?.length) onEvent({ type: "sources", data: { sources: result.sources } });
  onEvent({ type: "complete", data: { answer: result.answer } });
}

export async function listKnowledgeBases() {
  return requestJson("/api/kb");
}

/**
 * Get current model configuration from the backend.
 * @returns {Promise<{model: string, base_url: string|null, has_api_key: boolean}>}
 */
export async function getModelConfig() {
  return requestJson("/api/models/config");
}

export async function createKnowledgeBase({
  name,
  embeddingModel,
  files,
}) {
  const fd = new FormData();
  fd.append("name", name);
  fd.append("embedding_model", embeddingModel || "sentence-transformers/all-MiniLM-L6-v2");

  for (const f of files) {
    fd.append("files", f, f.name);
  }

  return requestJson("/api/kb", {
    method: "POST",
    body: fd,
  });
}

export async function queryKnowledgeBase({ kbId, question, modelConfig }) {
  const requestBody = {
    question,
    model_config_override: modelConfig
      ? {
          api_key: modelConfig.apiKey || null,
          model: modelConfig.model || null,
          base_url: modelConfig.baseUrl || null,
        }
      : null,
  };

  return requestJson(`/api/kb/${kbId}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestBody),
  });
}

export async function chatWithLlm({ messages, modelConfig }) {
  const requestBody = {
    messages,
    model_config_override: modelConfig
      ? {
          api_key: modelConfig.apiKey || null,
          model: modelConfig.model || null,
          base_url: modelConfig.baseUrl || null,
        }
      : null,
  };

  return requestJson("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestBody),
  });
}

/**
 * Stream a RAG query response with reasoning steps.
 * Falls back to non-streaming if streaming fails.
 * @param {Object} params - Query parameters
 * @param {string} params.kbId - Knowledge base ID
 * @param {string} params.question - The question to ask
 * @param {Object} [params.modelConfig] - Optional model config override
 * @param {(event: {type: string, data: object}) => void} onEvent - Callback for each SSE event
 * @returns {Promise<void>}
 */
export async function queryKnowledgeBaseStream({ kbId, question, modelConfig, onEvent }) {
  // Build request body with optional model config
  const requestBody = { 
    question,
    model_config_override: modelConfig ? {
      api_key: modelConfig.apiKey || null,
      model: modelConfig.model || null,
      base_url: modelConfig.baseUrl || null,
    } : null,
  };

  await requestStream(
    `/api/kb/${kbId}/query/stream`, requestBody,
    () => queryKnowledgeBase({ kbId, question, modelConfig }), onEvent,
  );
}

/**
 * Stream a chat response with token streaming.
 * Falls back to non-streaming if streaming fails.
 * @param {Object} params - Chat parameters
 * @param {Array<{role: string, content: string}>} params.messages - Chat history
 * @param {Object} [params.modelConfig] - Optional model config override
 * @param {(event: {type: string, data: object}) => void} onEvent - Callback for each SSE event
 * @returns {Promise<void>}
 */
export async function chatWithLlmStream({ messages, modelConfig, onEvent }) {
  // Build request body with optional model config
  const requestBody = {
    messages,
    model_config_override: modelConfig ? {
      api_key: modelConfig.apiKey || null,
      model: modelConfig.model || null,
      base_url: modelConfig.baseUrl || null,
    } : null,
  };

  await requestStream(
    "/api/chat/stream", requestBody,
    () => chatWithLlm({ messages, modelConfig }), onEvent,
  );
}
