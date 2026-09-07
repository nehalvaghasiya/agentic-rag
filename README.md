# Agentic RAG

Agentic RAG is a full-stack Retrieval-Augmented Generation (RAG) app:

- **Backend (FastAPI):** Upload files into a per-project knowledge base (KB), embed and store chunks in a local vector store, and query with **Server-Sent Events (SSE)** streaming (steps, sources, tokens).
- **Frontend (React + Vite):** Create/manage knowledge bases and chat with either:
  - a selected knowledge base (answers include citations), or
  - general chat (no KB).


## What you can do

- Create a knowledge base by uploading PDFs and text files.
- Ask questions and receive:
  - streaming reasoning steps (analyzing, rewriting, searching, grading, generating)
  - retrieved source snippets (citations)
  - token-by-token streaming answer
- Override the model configuration per request (API key/model/base URL) from the UI.

## Repository layout

- `backend/` — FastAPI API server and RAG pipeline
  - `backend/main.py` — FastAPI app entry point
  - `backend/routes.py` — HTTP routes (`/api/*`)
  - `backend/config.py` — settings (env) and prompt templates
  - `backend/models.py` — Pydantic request/response models and streaming event shapes
  - `backend/indexing/` — file loading, chunking, embedding
  - `backend/storage/` — KB manifest + persisted vector store
  - `backend/querying/` — RAG nodes and SSE streaming
- `frontend/` — React app (Vite) with a KB dashboard and chat UI

## Quickstart

### 1) Backend

Prereqs:

- Python 3.11+

Install dependencies (recommended: `uv`):

```bash
uv sync
```

Run the API server:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload
```

Open API docs:

- http://127.0.0.1:8001/docs

### 2) Frontend

Prereqs:

- Node.js 18+

Install dependencies (required before `npm run dev` / `npm run build`):

```bash
cd frontend
npm ci
```

If you prefer (or if you don't have a lockfile), use:

```bash
cd frontend
npm install
```

Run the dev server:

```bash
cd frontend
npm run dev
```

Build for production (optional):

```bash
cd frontend
npm run build
```

The UI defaults to calling the backend at `http://127.0.0.1:8001`.

To override:

```bash
cd frontend
VITE_API_URL=http://127.0.0.1:8001 npm run dev
```

## Configuration

Backend settings are loaded from environment variables (and optionally `.env`). See `.env.example`.

Common variables:

- `OPENAI_API_KEY` (optional)
  - If unset and `mode` is not deterministic, the backend will return an error for chat and will fall back to excerpt-only answers for KB queries.
- `OPENAI_MODEL` (optional)
- `OPENAI_BASE_URL` (optional)

Notes:

- The backend supports a **deterministic mode** (`Settings.mode = "deterministic"`) which disables LLM calls and uses hash embeddings. This is useful for tests and offline development.

## API overview

Base URL: `http://127.0.0.1:8001`

- `GET /api/health` — health check
- `GET /api/models/config` — current model config (no API key)
- `GET /api/kb` — list knowledge bases
- `POST /api/kb` — create KB from uploaded files (multipart form)
  - fields: `name`, `embedding_model`, `files[]`
- `POST /api/kb/{kb_id}/query/stream` — SSE stream for KB query
  - request body: `{ "question": "...", "model_config_override": {"api_key": ..., "model": ..., "base_url": ...} }`
  - SSE events: `step`, `sources`, `token`, `complete`, `error`
- `POST /api/chat/stream` — SSE stream for general chat
  - request body: `{ "messages": [{"role": "user|assistant", "content": "..."}], "model_config_override": ... }`

## How the RAG pipeline works (current backend)

1. **Indexing** (on KB creation)
   - Load documents from uploaded files (`.pdf` uses PyPDF loader; others treated as UTF-8 text)
   - Chunk documents using character windows with overlap (defaults: 800 chars, 120 overlap)
   - Embed chunks using either:
     - HuggingFace sentence-transformers (default), or
     - OpenAI embeddings if you choose an embedding model name that starts with `text-embedding-`
   - Persist KB metadata (`manifest.json`) and vectors (`vectors.pkl`) under `.data/kbs/<kb_id>/`

2. **Querying** (streamed)
   - Emit `step` events for UI
   - Optional query rewrite using the configured LLM
   - Retrieve top-k similar chunks from the vector store (cosine similarity)
   - Optional relevance grading using the LLM
   - Emit `sources` with snippets and similarity scores
   - Generate the final answer (stream tokens when possible)

## Development notes

- Data storage is local under `.data/` by default.
- CORS is enabled for common local dev origins.

## Troubleshooting

- Frontend can load without the backend running, but API calls will fail.
- If chat returns "LLM not configured", set `OPENAI_API_KEY` or use a request-level model override from the UI.

## License

MIT
