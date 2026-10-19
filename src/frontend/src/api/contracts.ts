import type { components, paths } from "./generated/schema";

export type Dto<Name extends keyof components["schemas"]> = components["schemas"][Name];
export type ExecutionEvent = Dto<"ExecutionEvent">;
export type SuccessEvent = Exclude<ExecutionEvent, { type: "error" }>;
export type OnEvent = (event: SuccessEvent) => void;
export type ApiPath = keyof paths;
export type MethodFor<P extends ApiPath> = {
  [M in keyof paths[P]]: M extends "get" | "post" ? M : never
}[keyof paths[P]];
type Operation<P extends ApiPath, M extends MethodFor<P>> =
  M extends keyof paths[P] ? NonNullable<paths[P][M]> : never;
export type JsonResponse<P extends ApiPath, M extends MethodFor<P>> =
  Operation<P, M> extends { responses: { 200: { content: { "application/json": infer T } } } }
    ? T : never;
export type RequestBody<P extends ApiPath, M extends MethodFor<P>> =
  Operation<P, M> extends { requestBody: { content: infer C } } ? C[keyof C] : never;
export type Endpoint<P extends ApiPath, M extends MethodFor<P>> = { path: P; method: M };

function endpoint<P extends ApiPath, M extends MethodFor<P>>(path: P, method: M): Endpoint<P, M> {
  return { path, method };
}

export const endpoints = {
  listKnowledgeBases: endpoint("/api/kb", "get"),
  createKnowledgeBase: endpoint("/api/kb", "post"),
  modelConfig: endpoint("/api/models/config", "get"),
  query: endpoint("/api/kb/{kb_id}/query", "post"),
  queryStream: endpoint("/api/kb/{kb_id}/query/stream", "post"),
  chat: endpoint("/api/chat", "post"),
  chatStream: endpoint("/api/chat/stream", "post"),
};

export function assertNever(value: never): never {
  throw new Error(`Unhandled event: ${String(value)}`);
}
