# Integrated chat frontend

Use Node 24/npm 11. From the repository root:

```bash
uv sync --group dev
npm --prefix frontend ci
npm run dev
```

The command also works from this directory. It supervises Vite, FastAPI, and the ingestion worker, provisions/migrates local PostgreSQL on first use, and retains data on restart. The application opens at http://127.0.0.1:5173/. Existing model settings in the root `.env` are passed to Python only. See the root README for existing database credentials and authenticated deployments.

**Knowledge Bases** in the sidebar opens `/kb`, the searchable library of existing bases. Dashboards support additional uploads, document preview/download, and confirmed document/base deletion; the chat composer links to its attached base with **Manage knowledge base**. PDFs use the native browser viewer with a text fallback. Other formats show paginated extracted text.

When upgrading, stop the old API and worker and restart `npm run dev` so database migration 003 is applied. Separately managed deployments must run `uv run agentic-rag migrate` with existing database credentials before starting the updated services. Existing documents do not need re-indexing.

One chat handles direct LLM, fast retrieval, and agentic research. `/agent` redirects to chat. Answers show compact document/tool citation chips and Copy, Regenerate, and More controls. Open **More → View sources** or select a citation to inspect passages in the right panel; **Response details** and **View activity** expose model, timing, grounding, coverage, and execution information on demand. The panel becomes an overlay on narrower screens, and navigation moves into a mobile drawer.

The composer groups the message, a searchable knowledge-base picker, model picker, and **Deep analysis** toggle in one surface. The settings icon next to an attached base opens its dashboard; the picker also links to the knowledge-base library. Select **General chat** to detach the base. Press Enter to send or Shift+Enter for a new line; the field grows with the draft. Paper-plane and solid-square controls send and stop responses. Configuration changes retain the draft, and sending waits for an in-progress knowledge-base selection to finish.

Regenerate creates a fresh answer version in the latest reply, preserving previous versions without duplicating the question. Its version selector persists the answer used for the next message. Earlier turns allow version inspection while retaining the context used by their existing follow-ups. Failed and cancelled attempts preserve the previous answer. Versions, source access checks, and selection survive a PostgreSQL restart; existing conversations are treated as single-version answers without a schema migration.

```bash
npm run dev:web             # Vite only; requires an already-running API
npm run lint
npm run type-check
npm test
npm run build
npm run test:e2e:install
npm run test:e2e
```

Browser tests start disposable frontend/backend processes with scripted providers. Set `AGENTIC_RAG_TEST_DATABASE_URL` to a disposable migrated pgvector application database to include restart durability in the browser journey. Each test uses a different tenant. Without it, browser fixtures use ephemeral storage. Provider credentials and user `.data` are never used by these tests.

Set `AGENTIC_RAG_E2E_BUILD=1` to exercise a production build in the browser harness. Each test builds into its disposable temporary directory and runs Vite preview with that test's API address. The response-control journeys also capture light/dark layouts at phone, tablet, and desktop sizes.

`contracts/openapi.json` is the v2 authority. `npm run generate:api-types` regenerates the chat declarations after `make contracts`. The v2 client validates HTTP responses and SSE envelopes against that same schema. Legacy declarations/client tests remain during the compatibility release; the chat does not call legacy endpoints.

## Dependency security

The frontend uses Vite 8, React plugin 6, Vitest 5, and Tailwind 4 with its Vite
integration. The legacy Tailwind PostCSS configuration is removed; the existing
JavaScript theme configuration is loaded explicitly from the CSS entrypoint.

```bash
npm ci
npm audit
npm run test:security
npm run lint
npm run type-check
npm test
npm run build
```

Picomatch's published 4.0.7 release is affected by
[GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf).
Until an upstream fix is released, every consumer uses the private local
[security fork](vendor/picomatch/README.md). It retains the upstream MIT license
and has a small parser-token guard against repeated wildcard extglobs. The
security tests enforce installation of that fork and exercise the reported
inputs in a subprocess with a hard timeout. CI runs those tests and the full
npm audit, including development dependencies. Local fork code is assessed by
these regressions and provenance checks; npm audit covers registry packages.
See the fork README for upstream references and the removal procedure.
