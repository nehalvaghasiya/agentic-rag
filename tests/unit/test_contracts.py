"""Legacy facade and v2 routes reference real handlers, never missing placeholders."""

from agentic_rag.api.app import create_app
from agentic_rag.core.config import Settings


def test_all_primary_contracts_exist() -> None:
    paths = create_app(Settings(environment="demo")).openapi()["paths"]
    for path in (
        "/api/v2/kb",
        "/api/v2/kb/{kb_id}",
        "/api/v2/kb/{kb_id}/documents",
        "/api/v2/documents/{doc_id}/preview",
        "/api/v2/documents/{doc_id}/download",
        "/api/v2/runs",
        "/api/v2/runs/{run_id}/events",
        "/api/v2/sources/{evidence_id}",
        "/api/v2/admin/evals",
        "/api/kb",
        "/api/chat",
    ):
        assert path in paths, path
