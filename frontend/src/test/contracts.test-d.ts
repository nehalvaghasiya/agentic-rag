import { assertNever, type Dto, type RequestBody, type SuccessEvent } from "../api/contracts";

// These compile-time regressions run under tsc, not Vitest.
export function contractTypes(event: SuccessEvent) {
  switch (event.type) {
    case "step": return event.data.title;
    case "token": {
      // @ts-expect-error Token events do not carry final answers.
      const answer: string = event.data.answer;
      return event.data.token + answer;
    }
    case "sources": return event.data.sources[0]?.file_name;
    case "complete": return event.data.answer;
    default: return assertNever(event);
  }
}

export const query: RequestBody<"/api/kb/{kb_id}/query", "post"> = {
  question: "question",
  // @ts-expect-error Request field names come from the generated contract.
  modelConfig: {},
};

export const config: Dto<"ModelConfig"> = {
  // @ts-expect-error UI camelCase names cannot cross the API boundary.
  apiKey: "key",
};

export const upload: RequestBody<"/api/kb", "post"> = {
  name: "KB", embedding_model: "offline", files: [new Blob(["content"])],
};

export const injectedRole: Dto<"ChatMessage"> = {
  // @ts-expect-error Privileged and arbitrary roles are not public input.
  role: "system", content: "untrusted instructions",
};

export const canonicalChat: Dto<"ChatRequest"> = {
  messages: [{ role: "user", content: "question" }], model_config_override: null,
};

// @ts-expect-error query is a POST operation.
export type InvalidMethod = RequestBody<"/api/kb/{kb_id}/query", "get">;
