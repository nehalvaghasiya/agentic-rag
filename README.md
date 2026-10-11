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

- `src/backend/` — FastAPI API server and RAG pipeline
  - `src/backend/main.py` — FastAPI app entry point
  - `src/backend/routes.py` — HTTP routes (`/api/*`)
  - `src/backend/config.py` — settings (env) and prompt templates
  - `src/backend/models.py` — Pydantic request/response models and streaming event shapes
  - `src/backend/indexing/` — file loading, chunking, embedding
  - `src/backend/storage/` — KB manifest + persisted vector store
  - `src/backend/querying/` — RAG nodes and SSE streaming
- `src/frontend/` — React app (Vite) with a KB dashboard and chat UI

## Quickstart

### 1) Backend

Prereqs:

- Python 3.11+

Install the locked runtime dependencies with `uv`. The UI defaults to local
Sentence Transformers embeddings, which require the `local-embeddings` extra:

```bash
uv sync --locked --no-default-groups --extra local-embeddings
```

For hosted embeddings or deterministic development, install the core runtime:

```bash
uv sync --locked --no-default-groups
```

For hosted embeddings, set `OPENAI_API_KEY` and select a `text-embedding-*` model
when creating a knowledge base. For offline deterministic development, set
`MODE=deterministic` before starting the server. Core installs exclude PyTorch,
Transformers, and Sentence Transformers. Local models download weights on first
use; those model files are separate from the Python dependency lockfile.

Run these commands from the repository root. They install the backend package
along with its dependencies. To install development tools as well, omit
`--no-default-groups`; retain `--extra local-embeddings` when using local models.

Run the API server through uv so it uses the synced environment:

```bash
uv run --no-sync python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload
```

For server deployment, omit `--reload`. Repeating the core-only sync removes the
optional local embedding packages, so include the extra whenever syncing that
profile. No global `uvicorn` installation or activated shell is required.

Open API docs:

- http://127.0.0.1:8001/docs

### 2) Frontend

Prereqs:

- Node.js 24.21.0 (npm 11.19.0); the repository `.nvmrc` is authoritative

Install dependencies (required before `npm run dev` / `npm run build`):

```bash
cd src/frontend
npm ci
```

Run the dev server:

```bash
cd src/frontend
npm run dev
```

Build for production (optional):

```bash
cd src/frontend
npm run build
```

Run frontend quality checks:

```bash
cd src/frontend
npm run lint
npm test
npm run type-check
```

For interactive component-test development, run `npm run test:watch`. The
component suite uses local network fixtures and does not require the backend or
provider credentials.

Browser journey tests require the synced backend environment and a one-time
Chromium installation:

```bash
cd src/frontend
npm run test:e2e:install
npm run test:e2e
```

Each journey launches isolated frontend and backend fixtures and blocks external
provider traffic.

The UI defaults to calling the backend at `http://127.0.0.1:8001`.

To override:

```bash
cd src/frontend
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
- Runtime dependency and installed-wheel validation: [isolated smoke tests](tests/smoke/README.md).

### Required checks

Application projects live under `src/backend` and `src/frontend`; Python metadata,
backend tests, developer tools, and CI remain at the repository root. Python imports
still use `backend`. Install the backend before running it or its tests.

CI uses locked, fresh environments for quality checks, offline regression tests,
core/wheel package smoke tests, frontend component tests/build, and headless Chromium
journeys. The backend test/package matrix covers Python 3.11–3.13. CI installs no
local embedding packages or model weights. Frontend types retain the existing policy:
strict checks for TS/TSX files, without checking existing JavaScript.

For a prepared developer environment, run all check families from the root:

```bash
uv sync --locked
uv run --no-sync python -m devtools.check
```

The runner requires uv 0.12.1, a supported Python interpreter, the Node version in
`.nvmrc`, npm 11.19.0, actionlint 1.7.12 and ShellCheck 0.11.0 on `PATH`, Docker with
Buildx, installed frontend dependencies, and headless Chromium. Install frontend dependencies with
`npm ci` and the browser with `npm run test:e2e:install` from `src/frontend`.
For Linux x86_64, the verified installer for workflow tools is
`bash devtools/install_actionlint.sh INSTALL_DIRECTORY`; add that directory to `PATH`.
It installs both actionlint and ShellCheck. Other platforms can use the official
releases of both tools for their platform.

Local pytest uses the active Python version; package smoke tests cover all three
interpreters. CI performs the full regression matrix in clean environments. The
local runner never installs dependencies or rewrites source; frontend builds and
test reports are ignored artifacts.

Minimal backend installations are `uv sync --locked --no-default-groups --group test`
for regression tests and `uv sync --locked --no-default-groups --group quality` for
quality tools. The normal `uv sync --locked` retains the combined developer setup.

See [CI configuration, failure validation, and merge-protection rollout](.github/README.md).

## Troubleshooting

- Frontend can load without the backend running, but API calls will fail.
- If chat returns "LLM not configured", set `OPENAI_API_KEY` or use a request-level model override from the UI.

## License

MIT
