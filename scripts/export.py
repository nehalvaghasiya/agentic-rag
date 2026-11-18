"""Export versioned API OpenAPI contract and verify essential routes."""

import json
from pathlib import Path

from agentic_rag.api.app import create_app
from agentic_rag.core.config import Settings

EXPECTED = {
    "/api/v2/kb",
    "/api/v2/kb/{kb_id}",
    "/api/v2/kb/{kb_id}/documents",
    "/api/v2/documents/{doc_id}/preview",
    "/api/v2/documents/{doc_id}/download",
    "/api/v2/runs",
    "/api/v2/runs/{run_id}/events",
    "/api/v2/admin/evals",
}


def main() -> None:
    app = create_app(Settings(environment="demo", store="fake", provider="fake"))
    spec = app.openapi()
    missing = EXPECTED - spec["paths"].keys()
    if missing:
        raise SystemExit(f"Missing essential contracts: {sorted(missing)}")
    path = Path("contracts/openapi.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(spec, indent=2, sort_keys=True) + "\n"
    path.write_text(content, encoding="utf-8")
    print(f"Exported {len(spec['paths'])} API routes to {path}")


if __name__ == "__main__":
    main()
