"""One simple CLI: serve, worker, demo, eval, fetch-hf and validate."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from agentic_rag.core.config import Settings
from agentic_rag.core.runtime import RuntimeFactory
from agentic_rag.eval.report import ReportWriter
from agentic_rag.eval.runner import EvalRunner

ROOT = Path(__file__).resolve().parents[2]


async def main_async(command: str, config: Path | None = None) -> None:
    settings = Settings.load(config)
    if command == "migrate":
        from agentic_rag.data.migrate import migrate

        await migrate(settings)
        return
    runtime = RuntimeFactory(settings)
    try:
        await runtime.open()
        if command in {"demo", "eval"}:
            from agentic_rag.core.demo import run, seed

            await seed(runtime, Path(__file__).resolve().parent / "resources" / "demo")
            if command == "demo":
                print(json.dumps(await run(runtime), indent=2))
            else:
                report = await EvalRunner(runtime.agent, runtime.repo).run(
                    Path(__file__).resolve().parent / "resources" / "demo" / "questions.jsonl"
                )
                paths = ReportWriter().write(report, Path.cwd() / "reports" / "demo")
                print(json.dumps(report.modes, indent=2))
                print("Reports:", *(str(p) for p in paths))
        elif command == "eval-hf":
            raise ValueError("Use main() to pass the input path for eval-hf")
        elif command == "worker":
            await runtime.worker.run()
        elif command == "validate":
            print(json.dumps(settings.public(), indent=2))
        else:
            raise ValueError("Unsupported subcommand")
    finally:
        await runtime.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="agentic-rag")
    parser.add_argument(
        "command",
        choices=["serve", "worker", "demo", "eval", "eval-hf", "validate", "fetch-hf", "migrate"],
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--out", type=Path, default=Path("datasets/golden/ragbench_50.jsonl"))
    parser.add_argument("--input", type=Path, default=Path("datasets/golden/ragbench_50.jsonl"))
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        from agentic_rag.api.app import create_app

        uvicorn.run(create_app(Settings.load(args.config)), host=args.host, port=args.port)
    elif args.command == "eval-hf":
        from agentic_rag.eval.hf import HFEvaluator

        async def evaluate_hf() -> None:
            runtime = RuntimeFactory(Settings.load(args.config))
            try:
                await runtime.open()
                report = await HFEvaluator(runtime).run(args.input, args.limit)
                out = Path.cwd() / "reports" / "hf" / "comparison.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(json.dumps(report["modes"], indent=2))
                print("Report:", out)
            finally:
                await runtime.close()

        asyncio.run(evaluate_hf())
    elif args.command == "fetch-hf":
        from agentic_rag.core.hf import fetch

        fetch(args.limit, args.out)
    else:
        asyncio.run(main_async(args.command, args.config))


if __name__ == "__main__":
    main()
