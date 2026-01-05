# Agentic RAG Frontend

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

## Backend API

By default the UI calls the backend at `http://127.0.0.1:8001`.

To override:

```bash
cd frontend
VITE_API_URL=http://127.0.0.1:8001 npm run dev
```
