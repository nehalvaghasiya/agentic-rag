# Agentic RAG Frontend

## Prerequisites

- Node.js 24.21.0 (npm 11.19.0); the repository `.nvmrc` is authoritative

## Dev

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

## Build

Create a production build (outputs to `dist/`):

```bash
cd src/frontend
npm run build
```

## Quality checks

Run linting and strict checks for TypeScript source files:

```bash
cd src/frontend
npm run lint
npm run type-check
```

Run the headless component tests once, or keep Vitest running while developing:

```bash
cd src/frontend
npm test
npm run test:watch
```

Component tests use controlled API fixtures and do not require a running backend
or provider credentials.

Run the Chromium browser journeys after syncing the repository's backend
environment. Install the browser binary once:

```bash
cd src/frontend
npm run test:e2e:install
npm run test:e2e
```

Each browser test starts its own Vite and FastAPI processes with scripted
providers and disposable storage. It does not use provider credentials or
application data under `.data/`.

## Backend API

By default the UI calls the backend at `http://127.0.0.1:8001`.

To override:

```bash
cd src/frontend
VITE_API_URL=http://127.0.0.1:8001 npm run dev
```

## Typed API boundary

The client, adapters, and application state consume generated OpenAPI types and
validate responses and SSE events before use. See [the contract workflow](../../contracts/README.md)
for regeneration and drift checks. Generated declarations are checked in; ordinary
frontend tests and builds do not require a running backend.
