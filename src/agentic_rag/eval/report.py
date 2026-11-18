"""Safe evaluation artifact writer: machine JSON, markdown and static HTML."""

import html
import json
from dataclasses import asdict
from pathlib import Path

from agentic_rag.models.report import EvalReport


class ReportWriter:
    def write(self, report: EvalReport, path: Path) -> list[Path]:
        path.mkdir(parents=True, exist_ok=True)
        json_path = path / "metrics.json"
        json_path.write_text(json.dumps(asdict(report), indent=2, default=str), encoding="utf-8")
        modes = list(report.modes)
        names = sorted({key for mode in report.modes.values() for key in mode})
        lines = [
            "# Agentic RAG evaluation comparison",
            "",
            "Deterministic offline demo results are **not** real model-quality or production SLO claims.",
            "",
            "| Metric | " + " | ".join(modes) + " |",
            "|---|" + "---:|" * len(modes),
        ]
        for name in names:
            cells = [
                "N/A" if report.modes[mode].get(name) is None else f"{report.modes[mode][name]:.4f}"
                for mode in modes
            ]
            lines.append("| " + name + " | " + " | ".join(cells) + " |")
        markdown = "\n".join(lines) + "\n"
        md_path = path / "compare.md"
        md_path.write_text(markdown, encoding="utf-8")
        html_body = "\n".join(f"<p>{html.escape(line)}</p>" for line in lines)
        html_path = path / "compare.html"
        html_path.write_text(
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>RAG Evaluation</title></head><body>" + html_body + "</body></html>",
            encoding="utf-8",
        )
        cases_path = path / "cases.jsonl"
        cases_path.write_text(
            "".join(json.dumps(c, default=str) + "\n" for c in report.cases), encoding="utf-8"
        )
        return [json_path, md_path, html_path, cases_path]
