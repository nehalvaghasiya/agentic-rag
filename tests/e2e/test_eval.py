"""Full 40-case paired run produces report artifacts for three modes."""

from pathlib import Path

from agentic_rag.eval.report import ReportWriter
from agentic_rag.eval.runner import EvalRunner


async def test_eval_dry_run(runtime, principal, tmp_path: Path) -> None:
    cases = Path(__file__).resolve().parents[2] / "datasets" / "demo" / "questions.jsonl"
    report = await EvalRunner(runtime.agent, runtime.repo).run(cases, principal=principal)
    assert len(report.cases) == 120
    assert set(report.modes) == {"baseline", "advanced", "agentic"}
    assert report.modes["agentic"]["tool_call_count"] > 0
    assert report.modes["baseline"]["tool_call_count"] == 0
    paths = ReportWriter().write(report, tmp_path)
    assert all(path.exists() and path.stat().st_size > 20 for path in paths)
