# API and event contracts

Backend Pydantic models and FastAPI routes own the interface. `backend.contracts.API_VERSION`
is the version source (initially `1.0.0`) shared by the live OpenAPI document and exports.
`openapi.json` and `src/frontend/src/api/generated/schema.d.ts` are generated; do not
edit them by hand. The JSON fixtures are curated regression cases, not generated output.

With the locked backend environment and frontend dependencies installed, run from
the repository root using the Node version in `.nvmrc`:

```bash
uv run --no-sync python -m devtools.contracts generate
uv run --no-sync python -m devtools.contracts check
```

Generation never starts application services, reads `.env`, or needs provider
credentials. Check mode regenerates into temporary storage, reports differences,
and leaves committed artifacts untouched. Commit intentional model or route
changes together with regenerated artifacts, fixture updates, and consumer changes.
The required `contracts` CI job and local check runner detect stale artifacts.
Compatibility classification and automatic version-bump enforcement are not included.

The five SSE envelopes form `ExecutionEvent`, discriminated by `type`; `data`
references the same payload models used by the serializer. Streaming operations
document the union through `x-event-schema`. On the wire, the type remains the
SSE `event:` field and only the payload is emitted in `data:`.

The browser uses Ajv Draft 2020-12 to validate decoded JSON and events before
adapters or callbacks see them. Validation does not coerce, inject defaults, or
remove properties. Extra fields follow the model's schema. Format labels are
annotations: existing timestamp strings may omit offsets. Correlation-ID patterns,
error length limits, and other declared constraints still assert; correlation-header
matching and validation-detail eligibility are additional semantic checks.

The generator is pinned to openapi-typescript 6.7.6 because 7.13.0 declares a
TypeScript 5 peer dependency while this repository checks application code with
TypeScript 6. Both OpenAPI binary-format and octet-stream media annotations map
to `Blob`; wire datetimes remain strings.

Python and browser tests consume `fixtures/payloads.json`. Backend tests also
validate actual serialized HTTP responses and SSE frames against the committed
document, and TypeScript checks request fields and exhaustive event consumers.
