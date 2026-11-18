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

Install the locked runtime dependencies with `uv`. The default server embedding
model uses local Sentence Transformers, which require the `local-embeddings` extra:

```bash
uv sync --locked --no-default-groups --extra local-embeddings
```

For hosted embeddings or deterministic development, install the core runtime:

```bash
uv sync --locked --no-default-groups
```

For hosted embeddings, configure the provider and model as described below; no
local embedding extra is needed. For offline deterministic development, set
`MODE=deterministic` before starting the server. Core installs exclude PyTorch,
Transformers, and Sentence Transformers. Local models download weights on first
use; those model files are separate from the Python dependency lockfile.

Run these commands from the repository root. They install the backend package
along with its dependencies. To install development tools as well, omit
`--no-default-groups`; retain `--extra local-embeddings` when using local models.

Run the API server through uv so it uses the synced environment:

```bash
uv run --no-sync python -m uvicorn backend.main:create_app --factory --host 0.0.0.0 --port 8001 --reload
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

Runtime configuration is validated before the application or its services are
constructed. Invalid settings fail startup with a diagnostic naming the setting
and its required constraint, without echoing configuration values or credentials.

| Setting | Default | Constraint |
| --- | --- | --- |
| `CHUNK_SIZE` | `800` | Integer greater than or equal to 1 |
| `CHUNK_OVERLAP` | `120` | Integer greater than or equal to 0 and smaller than `CHUNK_SIZE` |
| `TOP_K` | `5` | Integer greater than or equal to 1 |
| `MAX_RETRIES` | `2` | Integer greater than or equal to 0; zero permits no retries |
| `MODE` | `production` | Exactly `production` or `deterministic` |

These limits have no hard maximums. For example, `CHUNK_SIZE=1` is valid with
`CHUNK_OVERLAP=0`; reducing chunk size below the default overlap also requires
adjusting overlap. Invalid values are rejected rather than clamped. Numeric
environment strings are parsed as integers; booleans and fractional values are
rejected. Empty and incorrectly capitalized modes are rejected.

Settings passed to `create_app(settings)` are revalidated without reloading the
environment or `.env`. Normal settings loading retains explicit argument,
environment, `.env`, then default precedence. `CORS_ORIGINS`, when set in the
environment or `.env`, must be a JSON array of strings.

`create_app()` reads a fresh settings snapshot when called. Storage initializes
during application startup, and lifespan shutdown releases application services
without deleting persisted knowledge bases. Importing backend modules does not
load settings or create storage directories.

For an embedded application or test, call `create_app(settings)` with explicit
`Settings` and run its ASGI lifespan. Each application owns its settings and store;
use different `data_dir` values to isolate persisted files. Tests can override
FastAPI dependencies or supply a `services_factory` that registers resource
cleanup on the provided `AsyncExitStack`. The former `backend.main:app` entrypoint
and singleton settings helpers have been replaced by this factory interface.

Common variables:

- `OPENAI_API_KEY` (optional)
  - If unset and `mode` is not deterministic, the backend will return an error for chat and will fall back to excerpt-only answers for KB queries.
- `OPENAI_MODEL` (optional)
- `OPENAI_BASE_URL` (optional)

### OpenAI-compatible embeddings (including OmniRouter)

Chat and embeddings can use the same router or separate endpoints and credentials.
For the OmniRouter endpoint at `http://localhost:20128/v1`, configure `.env` with:

```dotenv
OPENAI_MODEL=auto
OPENAI_BASE_URL=http://localhost:20128/v1
OPENAI_API_KEY=YOUR_NEW_API_KEY

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=openrouter/qwen/qwen3-embedding-8b
# Optional: defaults to OPENAI_BASE_URL when omitted or empty.
EMBEDDING_BASE_URL=http://localhost:20128/v1
# Optional: defaults to OPENAI_API_KEY when omitted or empty.
EMBEDDING_API_KEY=
```

Replace the API key placeholder with your router's key and restart the backend.
In Create Knowledge Base, leave **Embedding Model** on **Use server default** to
use `EMBEDDING_MODEL`, or select **Custom model…** and enter another model ID
served by the configured provider. The chat model (`auto` here) is independent of
the embedding model. Chat model overrides do not change KB embedding credentials.

`EMBEDDING_PROVIDER=openai` accepts arbitrary model IDs and sends plain text to
the endpoint's `/embeddings` route, requesting float vectors. Set the base URL
to the API root, including `/v1` when required, without the `/embeddings` suffix.
An empty chat API key is allowed at startup; hosted embeddings still require
either `EMBEDDING_API_KEY` or `OPENAI_API_KEY` to be set.

The default `EMBEDDING_PROVIDER=auto` preserves the original selection:
`text-embedding-*` models use the OpenAI-compatible client, and other model names
use local HuggingFace embeddings. Set `EMBEDDING_PROVIDER=huggingface` to always
use local models, and install the `local-embeddings` extra. `MODE=deterministic`
continues to use offline hash embeddings regardless of provider configuration.

Each KB retains its chosen embedding model for queries, even if the server's
default model changes. Keep its provider configuration pointing to the same
embedding service; changing an existing KB's embedding model or vector space
requires recreating that KB from its source documents.

Notes:

- The backend supports a **deterministic mode** (`Settings.mode = "deterministic"`) which disables LLM calls and uses hash embeddings. This is useful for tests and offline development.
- Production mode can start without an API key. Deterministic mode ignores
  provider credentials. Validation does not contact providers or load embedding
  models.

## API overview

Base URL: `http://127.0.0.1:8001`

- `GET /api/health` — health check
- `GET /api/models/config` — current model config (no API key)
- `GET /api/kb` — list knowledge bases
- `POST /api/kb` — create KB from uploaded files (multipart form)
  - fields: `name`, optional `embedding_model` (defaults to `EMBEDDING_MODEL`), `files[]`
- `POST /api/kb/{kb_id}/query/stream` — SSE stream for KB query
  - request body: `{ "question": "...", "model_config_override": {"api_key": ..., "model": ..., "base_url": ...} }`
  - SSE events: `step`, `sources`, `token`, `complete`, `error`
- `POST /api/chat/stream` — SSE stream for general chat
  - request body: `{ "messages": [{"role": "user|assistant", "content": "..."}], "model_config_override": ... }`

### Public JSON request limits (API 2.0.0)

Both regular and streaming chat/query endpoints use strict request models and
reject unsupported fields at the root, inside messages, and inside model overrides.
Client messages accept exactly `user` or `assistant`. Histories must end with a
user message; assistant greetings and consecutive messages with the same role are
supported. Both chat modes send the complete accepted history to the model.

| Input | Limit |
|---|---:|
| Question or individual message | 1–8,000 Unicode code points, containing non-whitespace text |
| Chat history | 1–50 messages, at most 64,000 content code points combined |
| Model identifier override | 1–256 characters when supplied |
| API key override | 1–4,096 characters when supplied |
| Base URL override | 1–2,048 characters when supplied |
| Raw JSON body | 1,048,576 bytes (1 MiB), inclusive |

Original text, indentation, and surrounding whitespace are preserved and count
toward the limits. Invalid histories are rejected; the server does not truncate
content or prune messages. Omitted or `null` override values use server defaults;
an empty override object is valid, while blank supplied strings are rejected.

Body bytes are counted as received before JSON decoding, including chunked bodies
and requests with misleading `Content-Length` headers. An oversized body returns
HTTP 413 `PAYLOAD_TOO_LARGE`. Invalid decoded fields return HTTP 422
`VALIDATION_ERROR`. Both failures precede request-specific storage/provider work
and the opening of SSE responses. Existing application startup and service lookup
remain separate from that work.

The server prepends its own system policy for chat and separates trusted rewrite,
grading, and answer instructions from user questions and retrieved excerpts.
Client-supplied system/developer/tool roles and policy fields are rejected.
Instruction-like text inside content stays ordinary dialogue or task data.

API 2.0.0 deliberately rejects formerly accepted roles and payloads. Deploy matching
frontend/backend contracts together. KB multipart uploads, provider URL allowlists,
rate limits, and output-size limits are outside these JSON request bounds.

### Safe failures and correlation

HTTP failures use one JSON envelope. SSE execution failures send the same envelope
as the data of a terminal `event: error` frame:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Some request fields are invalid. Check the field details.",
    "retryable": false,
    "correlation_id": "05ede9f0-4165-486c-a8d5-f1cd726b14c6",
    "details": [
      {"field": "question", "code": "required", "message": "This field is required."}
    ]
  }
}
```

Every application response includes a server-generated `X-Correlation-ID`, exposed
to allowed browser origins through CORS. The error body/event carries the same ID;
client-supplied IDs are ignored. Use this reference to find the matching internal
JSON diagnostic record. Reverse-proxy failures, network failures and CORS preflight
responses occur outside the application error boundary.

`details` is omitted for non-validation errors. Validation returns at most 20
issues, using declared field paths and indexes such as `messages[0].content`.
Issue codes are `required`, `invalid_type`, `invalid_json`, and `invalid_value`;
unknown paths become `request`. Submitted values, arbitrary input keys and raw
validator messages are never returned.

| Code | HTTP status | Retryable | Safe message |
|---|---:|:---:|---|
| `BAD_REQUEST` | 400 | No | The request could not be read. Check its format. |
| `NOT_FOUND` | 404 | No | The requested resource was not found. |
| `METHOD_NOT_ALLOWED` | 405 | No | This method is not supported for this endpoint. |
| `CONFLICT` | 409 | No | This request conflicts with the current resource state. Refresh before trying again. |
| `PAYLOAD_TOO_LARGE` | 413 | No | The request is too large. Reduce its size and try again. |
| `VALIDATION_ERROR` | 422 | No | Some request fields are invalid. Check the field details. |
| `RATE_LIMITED` | 429 | Yes | Too many requests. Try again later. |
| `QUOTA_EXCEEDED` | 429 | No | The provider quota is exhausted. Check billing or quota before trying again. |
| `MODEL_NOT_CONFIGURED` | 503 | No | Configure a model API key before trying again. |
| `SERVICE_UNAVAILABLE` | 503 | Yes | The service is temporarily unavailable. Try again later. |
| `PROVIDER_AUTH_ERROR` | 502 | No | The model provider rejected the credentials or access. Check the model settings. |
| `PROVIDER_REQUEST_ERROR` | 502 | No | The model provider rejected this request. Check the model settings. |
| `PROVIDER_UNAVAILABLE` | 503 | Yes | The model provider is temporarily unavailable. Try again later. |
| `PROVIDER_TIMEOUT` | 504 | Yes | The model provider did not respond in time. Try again later. |
| `PROVIDER_ERROR` | 502 | No | The model provider could not complete the request. |
| `INTERNAL_ERROR` | 500 | No | The request could not be completed because of an internal error. |
| `HTTP_ERROR` | Original status | No | The request could not be completed. |

Retryability is advisory: another attempt may succeed without changing the input,
configuration or quota. It does not authorize automatic replay or guarantee that a
failed mutation had no effect. Provider rate limits are retryable; exhausted quota
requires billing/quota changes. Provider credentials and access failures are
upstream failures, rather than application authentication failures.

Invalid requests, missing resources and unavailable services fail before a stream
opens. After SSE headers are sent, HTTP 200 indicates an open connection; only
`complete` indicates success. Execution failures, including idle queue timeouts
(30 seconds for chat, 60 for KB queries), end with exactly one `error` and no
`complete`. Optional rewriting/grading failures keep their existing fallbacks and
produce safe warning diagnostics. Missing-model chat fails with
`MODEL_NOT_CONFIGURED`; KB queries retain excerpt-only and empty-evidence answers.

The web client throws `ApiError` for HTTP and SSE failures, retaining `code`,
`message`, `retryable`, `correlationId`, `details`, and nullable `httpStatus`.
It displays the safe message, validation issues, retry guidance and reference.
`NETWORK_ERROR`, `INVALID_RESPONSE`, and `STREAM_INTERRUPTED` represent client-side
transport/protocol failures; their correlation ID is null unless a valid server
reference was received. Invalid response bodies and raw network exceptions are not
displayed. Existing non-streaming compatibility fallback is limited to failures
before a response is consumed; API errors and interrupted streams never replay it.

Internal diagnostics retain correlation, route template, operation, error category,
exception classes, numeric provider status and bounded module/function/line stack
locations. They exclude raw exception messages, locals, absolute paths, headers,
provider bodies, prompts, document contents and credentials. Startup configuration
failures retain their existing safe fail-fast behavior.

Backend and frontend error-contract changes must be deployed together. Legacy
HTTP `detail` and SSE message-only payloads are no longer supported. Successful
response formats are unchanged; no persistence migration is required.

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
- If chat returns `MODEL_NOT_CONFIGURED`, set `OPENAI_API_KEY` or use a request-level model override from the UI.

## License

MIT

## API contract generation

API models, SSE events, and frontend boundary types share a versioned generated
contract. See [the contract workflow](contracts/README.md) for regeneration commands,
validation behavior, and CI requirements.
