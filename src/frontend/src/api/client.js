const DEFAULT_API_URL = "http://127.0.0.1:8001";

export const API_URL = import.meta.env.VITE_API_URL || DEFAULT_API_URL;

async function requestJson(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
    },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }

  return res.json();
}

/**
 * Parse SSE events from a ReadableStream.
 * @param {ReadableStream} stream - The response body stream
 * @param {(event: {type: string, data: object}) => void} onEvent - Callback for each event
 */
async function parseSSE(stream, onEvent) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  console.log("[SSE] Starting to parse stream");

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        console.log("[SSE] Stream complete");
        break;
      }

      const chunk = decoder.decode(value, { stream: true });
      console.log("[SSE] Received chunk:", chunk);
      buffer += chunk;
      
      // SSE events are separated by double newlines
      const events = buffer.split("\n\n");
      buffer = events.pop() || ""; // Keep incomplete event in buffer

      for (const eventBlock of events) {
        if (!eventBlock.trim()) continue;
        
        const lines = eventBlock.split("\n");
        let eventType = null;
        let eventData = null;

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventType = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            try {
              eventData = JSON.parse(line.slice(6));
            } catch (e) {
              console.warn("[SSE] Failed to parse JSON:", line.slice(6), e);
            }
          }
        }

        if (eventType && eventData) {
          console.log("[SSE] Parsed event:", eventType, eventData);
          onEvent({ type: eventType, data: eventData });
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
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

  let res;
  try {
    res = await fetch(`${API_URL}/api/kb/${kbId}/query/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
  } catch (err) {
    // Fallback to non-streaming endpoint
    console.warn("Streaming failed, falling back to non-streaming:", err);
    const fallbackRes = await queryKnowledgeBase({ kbId, question, modelConfig });
    onEvent({ type: "step", data: { type: "generating", title: "Generating response", description: "Processing..." } });
    if (fallbackRes.sources?.length > 0) {
      onEvent({ type: "sources", data: { sources: fallbackRes.sources } });
    }
    onEvent({ type: "complete", data: { answer: fallbackRes.answer } });
    return;
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }

  if (!res.body) {
    // Fallback if browser doesn't support streaming
    console.warn("Browser doesn't support streaming, falling back");
    const fallbackRes = await queryKnowledgeBase({ kbId, question, modelConfig });
    onEvent({ type: "step", data: { type: "generating", title: "Generating response", description: "Processing..." } });
    if (fallbackRes.sources?.length > 0) {
      onEvent({ type: "sources", data: { sources: fallbackRes.sources } });
    }
    onEvent({ type: "complete", data: { answer: fallbackRes.answer } });
    return;
  }

  await parseSSE(res.body, onEvent);
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
  console.log("[chatWithLlmStream] Starting with messages:", messages);
  
  // Build request body with optional model config
  const requestBody = {
    messages,
    model_config_override: modelConfig ? {
      api_key: modelConfig.apiKey || null,
      model: modelConfig.model || null,
      base_url: modelConfig.baseUrl || null,
    } : null,
  };

  let res;
  try {
    res = await fetch(`${API_URL}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
    console.log("[chatWithLlmStream] Response status:", res.status);
  } catch (err) {
    // Fallback to non-streaming endpoint
    console.warn("Streaming failed, falling back to non-streaming:", err);
    const fallbackRes = await chatWithLlm({ messages, modelConfig });
    onEvent({ type: "step", data: { type: "generating", title: "Generating response", description: "Processing..." } });
    onEvent({ type: "complete", data: { answer: fallbackRes.answer } });
    return;
  }

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }

  if (!res.body) {
    // Fallback if browser doesn't support streaming
    console.warn("Browser doesn't support streaming, falling back");
    const fallbackRes = await chatWithLlm({ messages, modelConfig });
    onEvent({ type: "step", data: { type: "generating", title: "Generating response", description: "Processing..." } });
    onEvent({ type: "complete", data: { answer: fallbackRes.answer } });
    return;
  }

  await parseSSE(res.body, onEvent);
}
