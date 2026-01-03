const nowIso = () => new Date().toISOString();

export const supportedUploadTypesLabel = "PDF, DOCX, TXT, MD, CSV";

export const initialKnowledgeBases = [
  {
    id: "kb_deepseek_v1",
    name: "DeepSeek-v1",
    rankingStrategy: "Hybrid",
    embeddingModel: "text-embedding-3-large",
    chunkingStrategy: "Recursive (800/120)",
    lastModified: nowIso(),
    documents: [
      {
        id: "doc_deepseek_v3_pdf",
        name: "DeepSeek_V3.pdf",
        type: "pdf",
        size: 1_590_000,
        status: "STATE_ACTIVE",
        uploadedAt: nowIso(),
      },
    ],
  },
];

export const initialChatHistory = [
  {
    id: "chat_training_cost",
    kbId: "kb_deepseek_v1",
    title: "What was the total training cost…",
    updatedAt: nowIso(),
    messages: [
      {
        id: "m1",
        role: "user",
        content: "What was the total training cost for the latest run?",
        sources: [],
      },
      {
        id: "m2",
        role: "ai",
        content:
          "Based on the cost breakdown in the run summary, the total training cost is approximately **$1.59M**.\n\nIf you want, I can break it down by compute, storage, and overhead.",
        sources: [
          {
            fileName: "DeepSeek_V3.pdf",
            pageNumber: 5,
            snippetText:
              "…The run-level aggregate shows a total training cost of $1.59M, including compute (A100-hours), storage IO, and orchestration overhead…",
            highlight: "$1.59M",
          },
        ],
      },
    ],
  },
  {
    id: "chat_chunking",
    kbId: "kb_deepseek_v1",
    title: "How does chunking impact recall?",
    updatedAt: nowIso(),
    messages: [
      {
        id: "m3",
        role: "user",
        content:
          "How does chunking strategy impact retrieval recall in this setup?",
        sources: [],
      },
      {
        id: "m4",
        role: "ai",
        content:
          "Smaller chunks can improve recall (more granular matches), but may reduce precision if context is lost. A hybrid strategy often works best: moderate chunk size with overlap and reranking.\n\nIn this knowledge base, chunking is configured for balanced recall and coherence.",
        sources: [
          {
            fileName: "DeepSeek_V3.pdf",
            pageNumber: 12,
            snippetText:
              "…Chunk size and overlap materially affect recall; smaller chunks increase candidate matches, while overlap preserves context for ranking…",
            highlight: "Chunk size and overlap",
          },
        ],
      },
    ],
  },
];
