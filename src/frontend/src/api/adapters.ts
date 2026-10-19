import type { Dto } from "./contracts";

export type ModelSettings = { apiKey?: string; model?: string; baseUrl?: string | null };

export function serializeModelConfig(config?: ModelSettings | null): Dto<"ModelConfig"> | null {
  return config ? {
    api_key: config.apiKey || null,
    model: config.model || null,
    base_url: config.baseUrl || null,
  } : null;
}

export function normalizeDocument(document: Dto<"DocumentMeta">) {
  return {
    id: document.id, name: document.name, type: document.type, size: document.size,
    status: "Indexed", uploadedAt: document.uploaded_at,
  };
}

export function normalizeKb(kb: Dto<"KnowledgeBase">) {
  return {
    id: kb.id, name: kb.name, embeddingModel: kb.embedding_model,
    rankingStrategy: kb.ranking_strategy, chunkingStrategy: kb.chunking_strategy,
    createdAt: kb.created_at, lastModified: kb.last_modified ?? kb.created_at,
    fileCount: kb.file_count, totalSize: kb.total_size,
    documents: kb.documents.map(normalizeDocument),
  };
}

export function normalizeSource(source: Dto<"Source">) {
  return {
    fileName: source.file_name, pageNumber: source.page, chunkIndex: source.chunk,
    snippetText: source.snippet, highlight: null, score: source.score, metadata: source.metadata,
  };
}

export function normalizeModelConfig(config: Dto<"ModelConfigResponse">) {
  return { model: config.model, baseUrl: config.base_url, hasApiKey: config.has_api_key };
}

export type KnowledgeBase = ReturnType<typeof normalizeKb>;
export type Source = ReturnType<typeof normalizeSource>;
