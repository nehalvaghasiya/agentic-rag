import { describe, expect, it, vi } from "vitest";
import { followRun, startRun, type ChatEvent } from "../api/chat";

const run = { id: "run-test", status: "running", mode: "direct", requested_mode: "auto", answer: "Hello" };
const timestamp = "2026-11-17T00:00:00Z";
const token = { id: 1, run_id: run.id, timestamp, type: "token", data: { token: "Hello" } };
const complete = { id: 2, run_id: run.id, timestamp, type: "complete", data: { ...run, status: "completed", supported: true } };
function stream(events: unknown[]) {
  return new Response(events.map(event => `data: ${JSON.stringify(event)}\n\n`).join(""), { headers: { "Content-Type": "text/event-stream" } });
}

describe("unified run boundary", () => {
  it("reconnects with the last event ID and deduplicates replay without creating another run", async () => {
    const fetch = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(stream([token]))
      .mockResolvedValueOnce(Response.json(run))
      .mockResolvedValueOnce(stream([token, complete]));
    const received: ChatEvent[] = [];
    await followRun(run.id, event => received.push(event), new AbortController().signal);
    expect(received.map(event => event.id)).toEqual([1, 2]);
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(fetch.mock.calls[2][1]?.headers).toEqual({ "Last-Event-ID": "1" });
    expect(fetch.mock.calls.every(([, options]) => !options?.method || options.method === "GET")).toBe(true);
  });

  it("rejects malformed activity and events from another run without replaying", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response('data: {"id":\n\n', { headers: { "Content-Type": "text/event-stream" } }));
    await expect(followRun(run.id, () => {}, new AbortController().signal)).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
    expect(fetch).toHaveBeenCalledTimes(1);
    fetch.mockResolvedValueOnce(stream([{ ...token, run_id: "different-run" }]));
    await expect(followRun(run.id, () => {}, new AbortController().signal)).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it("reuses the same idempotency key when run acceptance is lost to a network failure", async () => {
    const fetch = vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new TypeError("network"))
      .mockResolvedValueOnce(Response.json({ run_id: run.id, status: "accepted", events_url: `/api/v2/runs/${run.id}/events` }));
    await startRun({ question: "Hello", client_message_id: "stable-key", session_id: "chat-test" });
    expect(fetch.mock.calls[0][1]?.body).toEqual(fetch.mock.calls[1][1]?.body);
    expect(JSON.parse(String(fetch.mock.calls[1][1]?.body)).client_message_id).toBe("stable-key");
  });
});
