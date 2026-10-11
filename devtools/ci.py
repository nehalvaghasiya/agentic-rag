"""Small standard-library checks shared by CI and the local check runner."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_JOBS = (
    "workflow",
    "backend_quality",
    "backend_tests",
    "backend_package",
    "frontend",
    "browser",
)


def python_matrix() -> dict:
    return json.loads((ROOT / ".github/ci-matrix.json").read_text())


def check_layout() -> None:
    expected = (
        "src/backend/__init__.py",
        "src/backend/main.py",
        "src/frontend/package.json",
        "src/frontend/package-lock.json",
        "src/frontend/src/main.jsx",
        "src/frontend/e2e/harness.js",
        "pyproject.toml",
        "uv.lock",
        ".nvmrc",
    )
    missing = [name for name in expected if not (ROOT / name).is_file()]
    tracked = (
        subprocess.check_output(["git", "ls-files", "-z", "--", "backend", "frontend"], cwd=ROOT)
        .decode()
        .split("\0")
    )
    legacy = [name for name in tracked if name and (ROOT / name).exists()]
    if missing or legacy:
        raise ValueError(f"Invalid source layout: missing={missing}, legacy={legacy}")
    print("PASS: applications use src/backend and src/frontend", flush=True)


def check_frontend_lock() -> None:
    """Reject manifest drift even when npm can reuse a locked transitive package."""
    frontend = ROOT / "src/frontend"
    package = json.loads((frontend / "package.json").read_text())
    lock = json.loads((frontend / "package-lock.json").read_text())
    locked = lock.get("packages", {}).get("")
    if not isinstance(locked, dict):
        raise ValueError("Frontend lockfile must contain root package metadata")
    fields = (
        "dependencies",
        "devDependencies",
        "optionalDependencies",
        "peerDependencies",
        "peerDependenciesMeta",
        "engines",
    )
    changed = [field for field in fields if package.get(field, {}) != locked.get(field, {})]
    changed.extend(
        field for field in ("name", "version") if package.get(field) != locked.get(field)
    )
    if changed:
        raise ValueError(
            f"Frontend lockfile is stale for {', '.join(changed)}; refresh it with npm install"
        )
    print("PASS: frontend manifest matches lockfile metadata", flush=True)


def required_ci(raw_results: str) -> None:
    results = json.loads(raw_results)
    if not isinstance(results, dict) or set(results) != set(REQUIRED_JOBS):
        raise ValueError("Required CI received missing or unexpected jobs")
    rows = [f"| {name} | {results[name].get('result', 'missing')} |" for name in REQUIRED_JOBS]
    report = "| Check | Result |\n| --- | --- |\n" + "\n".join(rows) + "\n"
    print(report, flush=True)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a") as output:
            output.write(report)
    failed = [name for name in REQUIRED_JOBS if results[name].get("result") != "success"]
    if failed:
        raise ValueError(f"Required CI failed: {', '.join(failed)}")


def logged_command(command: list[str], log: Path | None) -> None:
    print(f"> {' '.join(command)}", flush=True)
    if log is None:
        subprocess.run(command, cwd=ROOT, check=True)
        return
    log.parent.mkdir(parents=True, exist_ok=True)
    with (
        log.open("w") as output,
        subprocess.Popen(
            command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        ) as process,
    ):
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            output.write(line)
        code = process.wait()
    if code:
        raise subprocess.CalledProcessError(code, command)


def package_checks(label: str | None, log_dir: Path | None) -> None:
    entries = python_matrix()["include"]
    selected = [entry for entry in entries if label is None or entry["label"] == label]
    if not selected:
        raise ValueError(f"Unsupported package-test Python version: {label}")
    for entry in selected:
        for target in ("core", "wheel"):
            tag = f"agentic-rag-ci:{target}-py{entry['label']}"
            commands = (
                (
                    "build",
                    [
                        "docker",
                        "buildx",
                        "build",
                        "--load",
                        "--progress=plain",
                        "--no-cache-filter",
                        "core,wheel-build",
                        "--target",
                        target,
                        "--build-arg",
                        f"PYTHON_IMAGE={entry['image']}",
                        "-f",
                        "tests/smoke/Dockerfile",
                        "-t",
                        tag,
                        ".",
                    ],
                ),
                ("runtime", ["docker", "run", "--rm", "--network", "none", tag]),
            )
            for stage, command in commands:
                log = log_dir / f"{target}-py{entry['label']}-{stage}.log" if log_dir else None
                logged_command(command, log)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("layout")
    commands.add_parser("frontend-lock")
    commands.add_parser("matrix")
    commands.add_parser("required")
    package = commands.add_parser("package")
    package.add_argument("--python", choices=[row["label"] for row in python_matrix()["include"]])
    package.add_argument("--log-dir", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "layout":
            check_layout()
        elif args.command == "frontend-lock":
            check_frontend_lock()
        elif args.command == "matrix":
            print(json.dumps(python_matrix(), separators=(",", ":")))
        elif args.command == "required":
            required_ci(os.environ.get("CI_RESULTS", "{}"))
        else:
            package_checks(args.python, args.log_dir)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"FAIL: {error}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
