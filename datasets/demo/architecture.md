# Architecture
Knowledge documents are parsed, split into chunks, and embedded before indexing. Dense search finds conceptually similar passages. BM25 keyword retrieval finds exact terms and identifiers. Hybrid search combines both rankings with reciprocal rank fusion. A reranker selects high-quality evidence for grounded answer generation. Every source citation refers to a versioned chunk ID.
