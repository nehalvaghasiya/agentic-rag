import { http, HttpResponse } from "msw";

import { API_URL } from "../api/client";
import {
  chatEventsFixture,
  knowledgeBaseFixture,
  modelConfigFixture,
  serializeSseEvents,
} from "./fixtures";

export const capturedRequests = {
  chat: [],
};

export function resetCapturedRequests() {
  capturedRequests.chat.length = 0;
}

export function createSseResponse(events, init = {}) {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "text/event-stream");
  headers.set("Cache-Control", "no-cache");

  return new HttpResponse(serializeSseEvents(events), {
    ...init,
    headers,
  });
}

export function createChatStreamHandler({
  events = chatEventsFixture,
  onRequest,
} = {}) {
  return http.post(`${API_URL}/api/chat/stream`, async ({ request }) => {
    const body = await request.json();
    capturedRequests.chat.push(body);
    onRequest?.(body);
    return createSseResponse(events);
  });
}

export function createChatStreamErrorHandler({
  status = 503,
  message = "Fixture provider unavailable",
} = {}) {
  return http.post(`${API_URL}/api/chat/stream`, () =>
    HttpResponse.text(message, { status })
  );
}

export const handlers = [
  http.get(`${API_URL}/api/models/config`, () =>
    HttpResponse.json(modelConfigFixture)
  ),
  http.get(`${API_URL}/api/kb`, () =>
    HttpResponse.json([knowledgeBaseFixture])
  ),
  createChatStreamHandler(),
];
