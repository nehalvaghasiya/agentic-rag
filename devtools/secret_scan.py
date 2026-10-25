"""Scan staged content or full history without publishing scanner output."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import NoReturn, TypedDict

VERSION = "8.30.1"
TIMEOUT_SECONDS = 120
FINDINGS_EXIT_CODE = 10


class ScanError(Exception):
    """A fixed, value-free diagnostic suitable for publication."""


class Finding(TypedDict):
    file: str
    line: int
    rule: str
    commit: str
    secret: str


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise ScanError("Invalid secret-scan arguments; use --help for usage.")


def run_private(command: list[str], root: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Keep subprocess output and exceptions inside the reporting boundary."""
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GITLEAKS_")
    }
    try:
        return subprocess.run(
            command,
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise ScanError("Secret scan timed out; no complete result is available.") from None
    except (OSError, UnicodeError):
        raise ScanError(
            "Cannot execute secret scanning tools; check Git and Gitleaks installation."
        ) from None


def verify_version() -> None:
    result = run_private(["gitleaks", "version"])
    if result.returncode or result.stderr.strip() or result.stdout.strip() != VERSION:
        raise ScanError("Secret scanning requires Gitleaks 8.30.1; run the verified installer.")


def repository_root() -> Path:
    result = run_private(["git", "rev-parse", "--show-toplevel"])
    if result.returncode:
        raise ScanError("Run secret scanning inside a Git working tree.")
    return Path(result.stdout.rstrip("\r\n"))


def sanitize_finding(raw: object) -> Finding:
    if not isinstance(raw, dict):
        raise ScanError("Secret scanner returned an invalid finding.")
    filename = raw.get("File")
    line = raw.get("StartLine")
    rule = raw.get("RuleID")
    commit = raw.get("Commit", "")
    if (
        not isinstance(filename, str)
        or not filename
        or PurePosixPath(filename).is_absolute()
        or ".." in PurePosixPath(filename).parts
        or "\0" in filename
        or type(line) is not int
        or line < 1
        or not isinstance(rule, str)
        or re.fullmatch(r"[a-zA-Z0-9_.-]{1,100}", rule) is None
        or not isinstance(commit, str)
        or (commit and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit) is None)
    ):
        raise ScanError("Secret scanner returned invalid finding locations.")
    return Finding(file=filename, line=line, rule=rule, commit=commit, secret="[REDACTED]")


def scan(mode: str, root: Path) -> list[Finding]:
    verify_version()
    ignore_file = root / ".gitleaksignore"
    if ignore_file.exists() or ignore_file.is_symlink():
        # The pinned scanner always reads source/.gitleaksignore, even when its
        # ignore-path flag points elsewhere. Reject it instead of suppressing leaks.
        raise ScanError("Remove .gitleaksignore; use reviewed rule-specific policy allowlists.")
    if mode == "history":
        shallow = run_private(["git", "rev-parse", "--is-shallow-repository"], root)
        if shallow.returncode or shallow.stdout.strip() != "false":
            raise ScanError("History scanning requires a full clone; fetch with --unshallow first.")
    # Do not silently consume a local .gitleaksignore as an additional policy.
    with TemporaryDirectory(prefix="secret-scan-") as ignore_directory:
        command = [
            "gitleaks",
            "git",
            "--config",
            str(root / ".gitleaks.toml"),
            "--redact=100",
            "--ignore-gitleaks-allow",
            "--gitleaks-ignore-path",
            ignore_directory,
            "--no-banner",
            "--no-color",
            "--log-level=error",
            f"--exit-code={FINDINGS_EXIT_CODE}",
            f"--timeout={TIMEOUT_SECONDS - 5}",
            "--report-format=json",
            "--report-path=-",
        ]
        if mode == "staged":
            command.extend(["--pre-commit", "--staged"])
        elif mode == "history":
            command.append("--log-opts=--full-history --all -m --no-ext-diff --no-textconv")
        else:
            raise ScanError("Unsupported secret scan mode.")
        result = run_private([*command, "."], root)
    # Gitleaks can log fragment errors without returning a failing exit code.
    # At error log level, any stderr means a complete scan is not established.
    if result.returncode not in (0, FINDINGS_EXIT_CODE) or result.stderr.strip():
        raise ScanError(
            "Secret scanner failed; no complete result is available. Check installation and policy."
        )
    try:
        raw = json.loads(result.stdout)
    except ValueError:
        raise ScanError("Secret scanner returned an invalid report.") from None
    # Gitleaks serializes a nil findings slice as JSON null on clean scans.
    if raw is None and result.returncode == 0:
        raw = []
    if not isinstance(raw, list) or bool(raw) != (result.returncode == FINDINGS_EXIT_CODE):
        raise ScanError("Secret scanner returned an inconsistent report.")
    findings = [sanitize_finding(item) for item in raw]
    unique = {json.dumps(finding, sort_keys=True): finding for finding in findings}
    return sorted(
        unique.values(), key=lambda row: (row["file"], row["line"], row["rule"], row["commit"])
    )


def publish(status: str, findings: list[Finding], message: str, report: Path | None) -> None:
    payload = {"status": status, "message": message, "findings": findings}
    if report is not None:
        report.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    lines = [
        message,
        *("  " + json.dumps(row, ensure_ascii=True, sort_keys=True) for row in findings),
    ]
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as output:
            output.write("<pre>" + html.escape("\n".join(lines)) + "</pre>\n")
    print("\n".join(lines), flush=True)


def main(argv: Sequence[str] | None = None) -> int:
    report = None
    try:
        parser = SafeArgumentParser(description=__doc__)
        parser.add_argument("mode", choices=("staged", "history"))
        parser.add_argument("--report", type=Path, help="write a sanitized JSON report")
        args = parser.parse_args(argv)
        report = args.report
        findings = scan(args.mode, repository_root())
        code = 1 if findings else 0
        status = "findings" if findings else "clean"
        message = (
            f"FAIL: secret scan found {len(findings)} finding(s). See SECURITY.md for remediation."
            if findings
            else "PASS: secret scan completed with no findings."
        )
    except ScanError as error:
        code, status, findings, message = 2, "error", [], f"ERROR: {error}"
    except (OSError, ValueError, KeyboardInterrupt):
        code, status, findings, message = 2, "error", [], "ERROR: Secret scan could not complete."
    try:
        publish(status, findings, message, report)
    except OSError:
        print("ERROR: Cannot write sanitized secret scan diagnostics.", flush=True)
        return 2
    return code


if __name__ == "__main__":
    raise SystemExit(main())
