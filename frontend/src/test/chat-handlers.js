import { http, HttpResponse } from "msw";
import { chatEventsFixture, errorFixture, knowledgeBaseFixture } from "./fixtures";

const timestamp = "2026-11-17T00:00:00Z";
const sessions = new Map();
const runs = new Map();
const streams = new Map();
let counter = 0;
let knowledge = [];
export const runRequests = [];
export function resetChatFixtures() {
  sessions.clear(); runs.clear(); streams.clear(); counter = 0; runRequests.length = 0;
  knowledge = [{ id: knowledgeBaseFixture.id, name: knowledgeBaseFixture.name, embedding_model: "deterministic",
    can_delete: true,
    created_at: timestamp, documents: knowledgeBaseFixture.documents.map(d => ({ id: d.id, title: d.name,
      content_type: d.type, size: d.size, status: "ready", version: 1, created_at: timestamp, can_delete: true })) }];
}
resetChatFixtures();
export function acceptFixtureUpload(kbId, files) {
  const kb = knowledge.find(k => k.id === kbId);
  const documents = files.map(file => ({ id: `doc_${++counter}`, title: file.name, content_type: file.type || "text/plain",
    size: file.size, status: "ready", version: 1, created_at: timestamp, can_delete: true }));
  kb.documents.push(...documents);
  return documents.map(doc => ({ id: `job-${doc.id}`, document_id: doc.id, status: "done" }));
}
function frame(runId, index, type, data) { return { id: index+1, run_id: runId, timestamp, type, data }; }
export function createRunHandler({ events = chatEventsFixture, onRequest } = {}) {
  return http.post("*/api/v2/runs", async ({ request }) => {
    const body = await request.json(); runRequests.push(body); onRequest?.(body);
    const id = `run_${++counter}`;
    const result = events.find(e => e.type === "complete")?.data || {};
    const answer = result.answer || "";
    const failure = events.find(e => e.type === "error");
    const run = { id, status: failure ? "failed" : "completed", mode: "direct", requested_mode: body.mode || "auto",
      execution_path: "direct", answer, citations: [], sources: [], model: "fixture-model", grounding: "model",
      served_from_cache: false, latency_ms: 10, session_id: body.session_id,
      assistant_message_id: `answer-${id}`, user_message_id: body.client_message_id, ...result };
    const initial = [frame(id, 0, "route", { title: "Direct LLM", execution_path: "direct", description: "Preparing a deterministic response." })];
    for (const event of events) {
      const type = event.type === "step" ? "generation" : event.type;
      const data = type === "complete" ? { ...run, supported: true } : type === "error" ? {
        code: event.data.error?.code || "RUN_FAILED", message: event.data.error?.message || "Response failed",
        correlation_id: event.data.error?.correlation_id || "fixture-error", retryable: false,
      } : event.data;
      initial.push(frame(id, initial.length, type, data));
    }
    runs.set(id, run); streams.set(id, initial);
    const session = sessions.get(body.session_id);
    if (session) {
      session.messages.push({ id: body.client_message_id, role: "user", content: body.question, status: "completed", run_id: id, created_at: timestamp, sources: [] });
      session.messages.push({ id: `answer-${id}`, role: "assistant", content: failure ? failure.data.error?.message || "Response failed" : answer, status: run.status, run_id: id,
        parent_user_message_id: body.client_message_id, versions: [{ run_id: id, status: run.status, created_at: timestamp }], created_at: timestamp, sources: run.sources });
    }
    return HttpResponse.json({ run_id: id, status: "accepted", events_url: `/api/v2/runs/${id}/events`, assistant_message_id: `answer-${id}`, user_message_id: body.client_message_id }, { status: 202 });
  });
}
export function createRunErrorHandler() {
  return http.post("*/api/v2/runs", () => HttpResponse.json(errorFixture(), { status: 503 }));
}
export const chatHandlers = [
  http.get("*/api/v2/settings/public", () => HttpResponse.json({ models: [{ id: "default", name: "fixture-model" }], ephemeral: false })),
  http.get("*/api/v2/kb", () => HttpResponse.json(knowledge)),
  http.get("*/api/v2/kb/:id", ({ params }) => {
    const kb = knowledge.find(k => k.id === params.id);
    return kb ? HttpResponse.json(kb) : HttpResponse.json({ error: { code: "ACCESS_DENIED", message: "Access denied" } }, { status: 403 });
  }),
  http.post("*/api/v2/kb", async ({ request }) => {
    const { name } = await request.json();
    const kb = { id: `kb_${++counter}`, name, embedding_model: "deterministic", created_at: timestamp, documents: [], can_delete: true };
    knowledge.push(kb); return HttpResponse.json(kb, { status: 201 });
  }),
  http.post("*/api/v2/kb/:id/documents", async ({ request, params }) => {
    // Avoid the Node/jsdom File brand mismatch in undici's multipart parser.
    const multipart = await request.text();
    const kb = knowledge.find(k => k.id === params.id);
    const documents = [...multipart.matchAll(/name="files"; filename="([^"]+)"/g)].map(match => ({ id: `doc_${++counter}`, title: match[1], content_type: "text/plain",
      size: 32, status: "ready", version: 1, created_at: timestamp, can_delete: true }));
    kb.documents.push(...documents);
    return HttpResponse.json(documents.map(doc => ({ id: `job-${doc.id}`, document_id: doc.id, status: "done" })), { status: 202 });
  }),
  http.delete("*/api/v2/kb/:id", ({ params }) => {
    knowledge = knowledge.filter(kb => kb.id !== params.id); return new HttpResponse(null, { status: 204 });
  }),
  http.get("*/api/v2/documents/:id/preview", ({ params, request }) => {
    const doc = knowledge.flatMap(kb => kb.documents).find(doc => doc.id === params.id);
    const offset = Number(new URL(request.url).searchParams.get("offset") || 0);
    return HttpResponse.json({ document_id: doc.id, version: 1, title: doc.title, offset, total_characters: 12,
      next_offset: offset === 0 ? 6 : null, sections: [{ text: offset === 0 ? "First." : "Last.", page: 1, section: null }] });
  }),
  http.get("*/api/v2/documents/:id/download", () => new HttpResponse("fixture original", { headers: { "Content-Type": "application/pdf" } })),
  http.delete("*/api/v2/documents/:id", ({ params }) => {
    knowledge = knowledge.map(kb => ({ ...kb, documents: kb.documents.filter(d => d.id !== params.id) }));
    return new HttpResponse(null, { status: 204 });
  }),
  http.get("*/api/v2/sessions", () => HttpResponse.json([...sessions.values()])),
  http.post("*/api/v2/sessions", async ({ request }) => {
    const body = await request.json();
    const session = { id: `session_${++counter}`, title: "New chat", kb_ids: body.kb_ids || [], messages: [], updated_at: timestamp, active_run_id: null, summary: "", summary_through: null };
    sessions.set(session.id, session); return HttpResponse.json(session, { status: 201 });
  }),
  http.get("*/api/v2/sessions/:id", ({ params }) => HttpResponse.json(sessions.get(params.id))),
  http.patch("*/api/v2/sessions/:id", async ({ request, params }) => {
    const session = sessions.get(params.id); Object.assign(session, await request.json()); return HttpResponse.json(session);
  }),
  http.delete("*/api/v2/sessions/:id", ({ params }) => { sessions.delete(params.id); return new HttpResponse(null, { status: 204 }); }),
  createRunHandler(),
  http.get("*/api/v2/runs/:id", ({ params }) => HttpResponse.json(runs.get(params.id))),
  http.get("*/api/v2/runs/:id/activity", ({ params }) => HttpResponse.json(streams.get(params.id))),
  http.get("*/api/v2/runs/:id/events", ({ params }) => new HttpResponse((streams.get(params.id) || []).map(event =>
    `id: ${event.id}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`).join(""), { headers: { "Content-Type": "text/event-stream" } })),
];
