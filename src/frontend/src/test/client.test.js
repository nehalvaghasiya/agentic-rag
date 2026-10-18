import { describe, expect, it, vi } from "vitest";

import {
  ApiError, chatWithLlm, chatWithLlmStream, describeApiError, queryKnowledgeBaseStream,
} from "../api/client";
import { correlationIdFixture, errorFixture, serializeSseEvents } from "./fixtures";

const privateText = "private-client-sentinel";
const messages = [{ role: "user", content: privateText }];
const headers = { "X-Correlation-ID": correlationIdFixture };

function sse(events) {
  return new Response(serializeSseEvents(events), {
    headers: { ...headers, "Content-Type": "text/event-stream" },
  });
}

describe("safe API error boundary", () => {
  it("retains structured HTTP errors and safe validation details", async () => {
    const payload = errorFixture({
      code: "VALIDATION_ERROR", message: "Some request fields are invalid. Check the field details.",
      retryable: false,
      details: [{ field: "messages[0].content", code: "required", message: "This field is required." }],
    });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(payload), { status: 422, headers }));
    const error = await chatWithLlm({ messages }).catch((error) => error);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      code: "VALIDATION_ERROR", retryable: false, httpStatus: 422,
      correlationId: correlationIdFixture, details: payload.error.details,
    });
    expect(describeApiError(error)).toContain("messages[0].content: This field is required.");
    expect(describeApiError(error)).toContain(`Reference: ${correlationIdFixture}`);
    expect(describeApiError(error)).not.toContain("You can try again later.");
  });

  it.each([privateText, JSON.stringify({ error: { message: privateText } }),
    JSON.stringify(errorFixture({ retryable: "yes", message: privateText })),
    JSON.stringify(errorFixture({ details: [{ field: privateText }] })),
    JSON.stringify(errorFixture({ correlation_id: "incorrect-id" })),
  ])("discards invalid or plain-text failures without rendering raw content", async (body) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(body, { status: 500, headers }));
    const error = await chatWithLlm({ messages }).catch((error) => error);
    expect(error).toMatchObject({ code: "INVALID_RESPONSE", retryable: false, correlationId: correlationIdFixture });
    expect(describeApiError(error)).not.toContain(privateText);
  });

  it("normalizes network failures without inventing a server reference", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error(privateText));
    const error = await chatWithLlm({ messages }).catch((error) => error);
    expect(error).toMatchObject({ code: "NETWORK_ERROR", retryable: true, correlationId: null, httpStatus: null });
    expect(describeApiError(error)).not.toContain(privateText);
    expect(describeApiError(new Error(privateText))).not.toContain(privateText);
  });

  it.each([chatWithLlmStream, queryKnowledgeBaseStream])("rejects SSE errors through the same ApiError and never replays", async (stream) => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(sse([
      { type: "token", data: { token: "partial" } },
      { type: "error", data: errorFixture({ code: "QUOTA_EXCEEDED", retryable: false }) },
      { type: "complete", data: { answer: "late success" } },
    ]));
    const onEvent = vi.fn();
    const error = await stream({ kbId: "kb_fixture", question: "question", messages, onEvent }).catch((error) => error);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: "QUOTA_EXCEEDED", retryable: false, correlationId: correlationIdFixture, httpStatus: null });
    expect(onEvent.mock.calls.map(([event]) => event.type)).toEqual(["token"]);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("never falls back on explicit HTTP errors from the streaming endpoint", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(errorFixture()), { status: 503, headers }));
    await expect(chatWithLlmStream({ messages, onEvent: vi.fn() })).rejects.toMatchObject({ code: "PROVIDER_UNAVAILABLE" });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("ends reading at completion and ignores later errors or tokens", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(sse([
      { type: "complete", data: { answer: "finished" } },
      { type: "error", data: errorFixture() },
      { type: "token", data: { token: privateText } },
    ]));
    const onEvent = vi.fn();
    await chatWithLlmStream({ messages, onEvent });
    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent.mock.calls[0][0]).toEqual({ type: "complete", data: { answer: "finished" } });
  });

  it("handles split UTF-8 and CRLF frames", async () => {
    const bytes = new TextEncoder().encode('event: complete\r\ndata: {"answer":"café"}\r\n\r\n');
    const split = bytes.indexOf(0xc3) + 1;
    const body = new ReadableStream({ start(controller) {
      controller.enqueue(bytes.slice(0, split));
      controller.enqueue(bytes.slice(split, -1));
      controller.enqueue(bytes.slice(-1));
      controller.close();
    } });
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(body, { headers: { ...headers, "Content-Type": "text/event-stream" } }));
    const onEvent = vi.fn();
    await chatWithLlmStream({ messages, onEvent });
    expect(onEvent.mock.calls[0][0].data.answer).toBe("café");
  });

  it.each([
    [serializeSseEvents([{ type: "token", data: { token: "partial" } }]), "STREAM_INTERRUPTED"],
    [`event: error\ndata: ${privateText}\n\n`, "INVALID_RESPONSE"],
    [serializeSseEvents([{ type: "error", data: { message: privateText } }]), "INVALID_RESPONSE"],
  ])("rejects truncated or malformed streams without replay", async (body, code) => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(body, { headers: { ...headers, "Content-Type": "text/event-stream" } }));
    const error = await chatWithLlmStream({ messages, onEvent: vi.fn() }).catch((error) => error);
    expect(error).toMatchObject({ code, correlationId: correlationIdFixture });
    expect(describeApiError(error)).not.toContain(privateText);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("retains the pre-response compatibility fallback", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error(privateText))
      .mockResolvedValueOnce(new Response(JSON.stringify({ answer: "fallback answer" })));
    const onEvent = vi.fn();
    await chatWithLlmStream({ messages, onEvent });
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(onEvent.mock.calls.at(-1)[0]).toEqual({ type: "complete", data: { answer: "fallback answer" } });
  });
});
