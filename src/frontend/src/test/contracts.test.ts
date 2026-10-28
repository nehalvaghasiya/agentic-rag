import { describe, expect, it, vi } from "vitest";
import fixtures from "../../../../contracts/fixtures/payloads.json";
import { normalizeKb, normalizeModelConfig, normalizeSource, serializeModelConfig } from "../api/adapters";
import { chatWithLlm, chatWithLlmStream, createKnowledgeBase, getModelConfig, listKnowledgeBases, queryKnowledgeBase, queryKnowledgeBaseStream } from "../api/client";
import { endpoints, type Dto } from "../api/contracts";
import { responseValidator, schemaValidator, validateEvent } from "../api/validation";
import { correlationIdFixture, errorFixture, serializeSseEvents } from "./fixtures";

const headers = { "X-Correlation-ID": correlationIdFixture };
const messages: Dto<"ChatMessage">[] = [{ role: "user", content: "question" }];
const kbValidator = responseValidator(endpoints.createKnowledgeBase);

function knowledgeBase(): Dto<"KnowledgeBase"> {
  const payload: unknown = fixtures[0].payload;
  if (!kbValidator(payload)) throw new Error("Invalid knowledge base fixture");
  return payload;
}

describe("shared contract fixtures", () => {
  it.each(fixtures)("$name", ({ schema, payload, valid }) => {
    const before = JSON.stringify(payload);
    expect(schemaValidator(schema)(payload)).toBe(valid);
    expect(JSON.stringify(payload)).toBe(before);
  });

  it("reuses operation validators and requires defaults emitted by the server", () => {
    expect(responseValidator(endpoints.createKnowledgeBase)).toBe(kbValidator);
    expect(kbValidator({ ...knowledgeBase(), documents: undefined })).toBe(false);
    expect(kbValidator({ ...knowledgeBase(), file_count: "0" })).toBe(false);
  });

  it.each(["x", "👋"])("counts Unicode code points in request schemas (%s)", (character) => {
    const query = schemaValidator("#/components/schemas/QueryRequest");
    const message = schemaValidator("#/components/schemas/ChatMessage");
    expect(query({ question: character.repeat(8000) })).toBe(true);
    expect(query({ question: character.repeat(8001) })).toBe(false);
    expect(message({ role: "user", content: character.repeat(8000) })).toBe(true);
    expect(message({ role: "user", content: character.repeat(8001) })).toBe(false);
  });

  it("enforces list and override bounds without injecting defaults", () => {
    const chat = schemaValidator("#/components/schemas/ChatRequest");
    const messages = Array.from({ length: 50 }, () => ({ role: "user", content: "x" }));
    expect(chat({ messages })).toBe(true);
    expect(chat({ messages: [...messages, messages[0]] })).toBe(false);
    const config = schemaValidator("#/components/schemas/ModelConfig");
    for (const [field, limit] of [["api_key", 4096], ["model", 256], ["base_url", 2048]] as const) {
      expect(config({ [field]: "x".repeat(limit) })).toBe(true);
      expect(config({ [field]: "x".repeat(limit + 1) })).toBe(false);
    }
  });
});

describe("typed presentation adapters", () => {
  it("preserves zero values, naive timestamps, and the declared last-modified fallback", () => {
    const kb = knowledgeBase();
    const normalized = normalizeKb(kb);
    expect(normalized.fileCount).toBe(0);
    expect(normalized.totalSize).toBe(0);
    expect(normalized.lastModified).toBe(kb.created_at);
    expect(normalized.createdAt).toBe("2026-01-02T03:04:05");
    expect(normalized.documents[0]).toMatchObject({ status: "Indexed", size: 0, uploadedAt: kb.created_at });
    expect(normalizeKb({ ...kb, ranking_strategy: "", chunking_strategy: "" })).toMatchObject({
      rankingStrategy: "", chunkingStrategy: "",
    });
  });

  it("preserves nullable citation fields, zero scores, and metadata", () => {
    const source: Dto<"Source"> = {
      file_name: "notes.txt", page: null, chunk: 0, snippet: "", score: 0,
      metadata: { nested: [1, true, null] },
    };
    expect(normalizeSource(source)).toEqual({
      fileName: "notes.txt", pageNumber: null, chunkIndex: 0, snippetText: "", score: 0,
      metadata: source.metadata, highlight: null,
    });
    expect(normalizeSource({ ...source, chunk: null, score: null })).toMatchObject({ chunkIndex: null, score: null });
  });

  it("converts model configuration in one place", () => {
    expect(serializeModelConfig(null)).toBeNull();
    expect(serializeModelConfig({ apiKey: "key", model: "model", baseUrl: "url" }))
      .toEqual({ api_key: "key", model: "model", base_url: "url" });
    expect(serializeModelConfig({})).toEqual({ api_key: null, model: null, base_url: null });
    expect(normalizeModelConfig({ model: "model", base_url: null, has_api_key: false }))
      .toEqual({ model: "model", baseUrl: null, hasApiKey: false });
  });
});

describe("runtime response boundary", () => {
  it.each([chatWithLlmStream, queryKnowledgeBaseStream])(
    "preserves HTTP 413/422 validation errors without fallback", async (stream) => {
      for (const [status, code] of [[413, "PAYLOAD_TOO_LARGE"], [422, "VALIDATION_ERROR"]] as const) {
        const payload = errorFixture({ code, retryable: false });
        const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(payload), { status, headers }));
        const onEvent = vi.fn();
        await expect(stream({ messages, kbId: "kb", question: "q", onEvent }))
          .rejects.toMatchObject({ code, httpStatus: status, retryable: false, correlationId: correlationIdFixture });
        expect(onEvent).not.toHaveBeenCalled();
        expect(fetch).toHaveBeenCalledTimes(1);
        fetch.mockRestore();
      }
    },
  );
  it.each([
    ["chat", () => chatWithLlm({ messages }), { answer: 42 }],
    ["query", () => queryKnowledgeBase({ kbId: "kb", question: "q" }), { answer: "ok", sources: [{}] }],
    ["list", () => listKnowledgeBases(), [{}]],
    ["configuration", () => getModelConfig(), { model: "x", base_url: null, has_api_key: "yes" }],
    ["creation", () => createKnowledgeBase({ name: "KB", files: [] }), {}],
  ] as const)("rejects malformed successful %s responses", async (_, request, payload) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(payload), { headers }));
    await expect(request()).rejects.toMatchObject({ code: "INVALID_RESPONSE", correlationId: correlationIdFixture, httpStatus: 200 });
  });

  it("rejects camelCase aliases before adapters receive them", async () => {
    const { embedding_model: embeddingModel, ...rest } = knowledgeBase();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([{ ...rest, embeddingModel }]), { headers }));
    await expect(listKnowledgeBases()).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });

  it("serializes the generated multipart body and preserves filenames", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(knowledgeBase()), { headers }));
    await createKnowledgeBase({ name: "KB", embeddingModel: "offline", files: [new File(["text"], "notes.txt")] });
    const body = fetch.mock.calls[0][1]?.body;
    expect(body).toBeInstanceOf(FormData);
    if (!(body instanceof FormData)) throw new Error("Missing multipart body");
    expect(body.get("name")).toBe("KB");
    expect(body.get("embedding_model")).toBe("offline");
    expect(body.get("files")).toMatchObject({ name: "notes.txt" });
  });

  it.each([undefined, ""])("uses the server embedding default when no model is selected (%s)", async (embeddingModel) => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(knowledgeBase()), { headers }));
    await createKnowledgeBase({ name: "KB", embeddingModel, files: [new File(["text"], "notes.txt")] });
    const body = fetch.mock.calls[0][1]?.body;
    if (!(body instanceof FormData)) throw new Error("Missing multipart body");
    expect(body.has("embedding_model")).toBe(false);
  });

  it.each(fixtures.filter((fixture) => !fixture.valid && fixture.schema.endsWith("/ExecutionEvent")))(
    "rejects $name before callbacks and never replays the request", async ({ payload }) => {
      const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(
        serializeSseEvents([payload]), { headers: { ...headers, "Content-Type": "text/event-stream" } },
      ));
      const onEvent = vi.fn();
      await expect(chatWithLlmStream({ messages, onEvent })).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
      expect(onEvent).not.toHaveBeenCalled();
      expect(fetch).toHaveBeenCalledTimes(1);
    },
  );

  it("rejects correlation mismatches and unexpected validation details", async () => {
    for (const payload of [errorFixture({ correlation_id: "00000000-0000-0000-0000-000000000000" }),
      errorFixture({ details: [{ field: "messages", code: "required", message: "Required." }] })]) {
      vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(payload), { status: 503, headers }));
      await expect(chatWithLlm({ messages })).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
    }
  });

  it("ignores comment heartbeats and accepts multiline JSON data", async () => {
    const body = ': heartbeat\n\nevent: complete\ndata: {\ndata: "answer": "finished"}\n\n';
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(body, { headers: { ...headers, "Content-Type": "text/event-stream" } }));
    const onEvent = vi.fn();
    await chatWithLlmStream({ messages, onEvent });
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith({ type: "complete", data: { answer: "finished" } });
  });

  it("does not synthesize fallback success from malformed JSON", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(new Response(JSON.stringify({ answer: 42 }), { headers }));
    const onEvent = vi.fn();
    await expect(chatWithLlmStream({ messages, onEvent })).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
    expect(onEvent).not.toHaveBeenCalled();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it.each(["complete", "error"])("cancels and unlocks the reader after %s", async (type) => {
    const cancel = vi.fn();
    const event = { type, data: type === "complete" ? { answer: "done" } : errorFixture() };
    const stream = new ReadableStream({
      start(controller) { controller.enqueue(new TextEncoder().encode(serializeSseEvents([event]))); },
      cancel,
    });
    const response = new Response(stream, { headers: { ...headers, "Content-Type": "text/event-stream" } });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(response);
    await chatWithLlmStream({ messages, onEvent: vi.fn() }).catch(() => {});
    expect(cancel).toHaveBeenCalledTimes(1);
    expect(response.body?.locked).toBe(false);
  });

  it("turns reader failures into interrupted errors without replay", async () => {
    const stream = new ReadableStream({ start(controller) { controller.error(new Error("private-sentinel")); } });
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(stream, {
      headers: { ...headers, "Content-Type": "text/event-stream" },
    }));
    await expect(chatWithLlmStream({ messages, onEvent: vi.fn() }))
      .rejects.toMatchObject({ code: "STREAM_INTERRUPTED", correlationId: correlationIdFixture });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("validates the compatibility fallback when the streaming response has no body", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(null))
      .mockResolvedValueOnce(new Response(JSON.stringify({ answer: "fallback" }), { headers }));
    const onEvent = vi.fn();
    await chatWithLlmStream({ messages, onEvent });
    expect(onEvent.mock.calls[onEvent.mock.calls.length - 1]?.[0]).toEqual({ type: "complete", data: { answer: "fallback" } });
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("rejects unexpected stream media types without replay", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ answer: "wrong transport" }), {
      headers: { ...headers, "Content-Type": "application/json" },
    }));
    await expect(chatWithLlmStream({ messages, onEvent: vi.fn() })).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("rejects non-JSON success bodies with a safe correlated error", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("private-sentinel", { headers }));
    await expect(chatWithLlm({ messages })).rejects.toMatchObject({
      code: "INVALID_RESPONSE", message: "The service returned an invalid response.",
      correlationId: correlationIdFixture,
    });
  });

  it("narrowly validates the complete event before delivery", () => {
    const event: unknown = { type: "complete", data: { answer: "" } };
    expect(validateEvent(event)).toBe(true);
  });
});
