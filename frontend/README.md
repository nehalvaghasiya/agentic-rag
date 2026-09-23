# Agentic RAG Frontend

## Prerequisites

- Node.js 24.21.0 (npm 11.19.0); the repository `.nvmrc` is authoritative

## Dev

Install dependencies (required before `npm run dev` / `npm run build`):

```bash
cd frontend
npm ci
```

If you prefer, use:

```bash
cd frontend
npm install
```

Run the dev server:

```bash
cd frontend
npm run dev
```

## Build

Create a production build (outputs to `dist/`):

```bash
cd frontend
npm run build
```

## Quality checks

Run linting and strict checks for TypeScript source files:

```bash
cd frontend
npm run lint
npm run type-check
```

Run the headless component tests once, or keep Vitest running while developing:

```bash
cd frontend
npm test
npm run test:watch
```

Component tests use controlled API fixtures and do not require a running backend
or provider credentials.

## Backend API

By default the UI calls the backend at `http://127.0.0.1:8001`.

To override:

```bash
cd frontend
VITE_API_URL=http://127.0.0.1:8001 npm run dev
```
