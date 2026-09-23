export const modelConfigFixture = {
  model: "fixture-model",
  base_url: null,
  has_api_key: false,
};

export const knowledgeBaseFixture = {
  id: "kb_fixture",
  name: "Fixture Knowledge Base",
  embedding_model: "deterministic",
  created_at: "2026-01-02T03:04:05.000Z",
  last_modified: "2026-01-03T04:05:06.000Z",
  file_count: 1,
  total_size: 2048,
  ranking_strategy: "Hybrid",
  chunking_strategy: "Recursive (800/120)",
  documents: [
    {
      id: "doc_fixture",
      name: "fixture-report.pdf",
      type: "pdf",
      size: 2048,
      uploaded_at: "2026-01-03T04:05:06.000Z",
    },
  ],
};

export const chatEventsFixture = [
  {
    type: "step",
    data: {
      type: "analyzing",
      title: "Analyzing request",
      description: "Preparing a deterministic response.",
    },
  },
  { type: "token", data: { token: "Fixture " } },
  { type: "token", data: { token: "answer." } },
  { type: "complete", data: { answer: "Fixture answer." } },
];

export function serializeSseEvents(events) {
  return events
    .map(({ type, data }) => `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`)
    .join("");
}
