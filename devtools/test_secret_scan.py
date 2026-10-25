"""Offline secret-gate regressions using synthetic, disposable Git repositories."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import random
import re
import shutil
import string
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from devtools import secret_scan
from devtools.ci import REQUIRED_JOBS, required_ci

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "devtools/secret_scan.py"


def synthetic_secret(family: str = "github") -> str:
    """Construct scanner-positive strings without storing complete credentials."""
    generator = random.Random(7419)

    def body(length: int) -> str:
        return "".join(generator.choices(string.ascii_letters + string.digits, k=length))

    if family == "github":
        return "gh" + "p_" + body(36)
    if family == "github-fine":
        return "github_" + "pat_" + body(82)
    if family == "openai":
        return "sk" + "-" + body(20) + "T3Bl" + "bkFJ" + body(20)
    if family == "openai-project":
        return "sk" + "-proj-" + body(74) + "T3Bl" + "bkFJ" + body(74)
    if family == "generic":
        return "".join(generator.choices("abcdef0123456789", k=64))
    if family == "private-key":
        return (
            "-----BEGIN "
            + "RSA PRIVATE "
            + "KEY-----\n"
            + body(128)
            + "\n-----END "
            + "RSA PRIVATE "
            + "KEY-----\n"
        )
    raise ValueError("Unknown fixture family")


class SecretScanIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        secret_scan.verify_version()
        if importlib.util.find_spec("pre_commit") is None:
            raise RuntimeError(
                "Install the locked hooks dependency group before running scanner tests."
            )

    def setUp(self) -> None:
        temporary = TemporaryDirectory(prefix="secret-gate-test-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.repo = self.directory / "repo"
        self.repo.mkdir()
        self.environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("GIT_", "GITLEAKS_", "PRE_COMMIT_"))
        }
        self.environment.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_AUTHOR_NAME="Secret gate test",
            GIT_AUTHOR_EMAIL="test@example.invalid",
            GIT_COMMITTER_NAME="Secret gate test",
            GIT_COMMITTER_EMAIL="test@example.invalid",
            GIT_TERMINAL_PROMPT="0",
            GITHUB_STEP_SUMMARY=str(self.directory / "summary.txt"),
            PRE_COMMIT_HOME=str(self.directory / "pre-commit"),
            PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
        )
        self.git("init", "-q")
        self.git("symbolic-ref", "HEAD", "refs/heads/main")
        shutil.copyfile(ROOT / ".gitleaks.toml", self.repo / ".gitleaks.toml")

    def command(
        self, arguments: list[str], *, check: bool = True, cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                arguments,
                cwd=cwd or self.repo,
                env=self.environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            raise self.failureException(
                "Fixture command could not complete; output withheld."
            ) from None
        if check and result.returncode:
            self.fail("Fixture command failed; output withheld.")
        return result

    def git(self, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return self.command(["git", *arguments], check=check)

    def stage(self, content: str, filename: str = "example.txt") -> None:
        (self.repo / filename).write_text(content, encoding="utf-8")
        self.git("add", "--", filename)

    def commit(self, message: str = "fixture") -> None:
        self.git("add", "--", ".gitleaks.toml")
        self.git("-c", "commit.gpgsign=false", "commit", "--no-verify", "-qm", message)

    def scan(
        self, mode: str = "staged", *, cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        return self.command(
            [
                sys.executable,
                str(WRAPPER),
                mode,
                "--report",
                str(self.directory / "report.json"),
            ],
            check=False,
            cwd=cwd,
        )

    def assert_redacted(self, result: subprocess.CompletedProcess[str], value: str) -> None:
        surfaces = [result.stdout, result.stderr]
        for filename in ("report.json", "summary.txt"):
            report = self.directory / filename
            if report.exists():
                surfaces.append(report.read_text(encoding="utf-8"))
        self.assertTrue(
            all(value not in surface for surface in surfaces), "Fixture value was exposed."
        )

    def assert_detected(self, value: str, *, mode: str = "staged") -> None:
        result = self.scan(mode)
        self.assertEqual(result.returncode, 1, "Synthetic secret was not rejected.")
        self.assert_redacted(result, value)
        self.assertTrue("[REDACTED]" in result.stdout, "Redacted location was missing.")

    def stub_scanner(self, program: str, *, version: str = secret_scan.VERSION) -> None:
        binaries = self.directory / "bin"
        binaries.mkdir(exist_ok=True)
        scanner = binaries / "gitleaks"
        scanner.write_text(
            f"#!{sys.executable}\nimport sys\n"
            f"if sys.argv[1:] == ['version']:\n    print({version!r})\n    sys.exit(0)\n" + program,
            encoding="utf-8",
        )
        scanner.chmod(0o700)
        self.environment["PATH"] = str(binaries) + os.pathsep + self.environment["PATH"]

    def test_provider_and_github_formats(self) -> None:
        for family in (
            "openai",
            "openai-project",
            "github",
            "github-fine",
            "generic",
            "private-key",
        ):
            with self.subTest(family=family):
                value = synthetic_secret(family)
                self.stage("API_KEY=" + value + "\n")
                self.assert_detected(value)

    def test_empty_index_and_clean_initial_commit(self) -> None:
        self.assertEqual(self.scan().returncode, 0)
        self.stage("Safe text\n")
        self.assertEqual(self.scan().returncode, 0)
        self.commit()
        self.assertEqual(self.scan("history").returncode, 0)

    def test_staged_secret_cannot_be_hidden_by_unstaged_cleanup(self) -> None:
        value = synthetic_secret()
        self.stage(value + "\n")
        (self.repo / "example.txt").write_text("Safe text\n", encoding="utf-8")
        self.assert_detected(value)

    def test_unstaged_secret_does_not_block_clean_index(self) -> None:
        self.stage("Safe text\n")
        (self.repo / "example.txt").write_text(synthetic_secret() + "\n", encoding="utf-8")
        self.assertEqual(self.scan().returncode, 0)

    def test_clean_rename_and_deletion(self) -> None:
        self.stage("Safe text\n")
        self.commit()
        self.git("mv", "example.txt", "renamed.txt")
        self.assertEqual(self.scan().returncode, 0)
        self.commit()
        self.git("rm", "renamed.txt")
        self.assertEqual(self.scan().returncode, 0)

    def test_deleted_historical_secret_and_metadata_are_redacted(self) -> None:
        value = synthetic_secret()
        self.stage(value + "\n")
        self.commit(value)
        self.stage("Safe text\n")
        self.commit()
        self.assert_detected(value, mode="history")
        payload = json.loads((self.directory / "report.json").read_text())
        finding = payload["findings"][0]
        self.assertEqual(set(finding), {"file", "line", "rule", "commit", "secret"})
        self.assertEqual(finding["file"], "example.txt")
        self.assertEqual(finding["line"], 1)
        self.assertTrue(bool(re.fullmatch(r"[0-9a-f]{40}", finding["commit"])))

    def test_secret_on_another_ref(self) -> None:
        self.stage("Safe text\n")
        self.commit()
        self.git("checkout", "-qb", "other")
        value = synthetic_secret()
        self.stage(value + "\n")
        self.commit()
        self.git("checkout", "-q", "main")
        self.assertEqual(self.scan().returncode, 0)
        self.assert_detected(value, mode="history")

    def test_secret_only_in_merge_resolution(self) -> None:
        self.stage("Base\n")
        self.commit()
        self.git("checkout", "-qb", "side")
        self.stage("Side\n")
        self.commit()
        self.git("checkout", "-q", "main")
        self.stage("Main\n")
        self.commit()
        merge = self.git("-c", "commit.gpgsign=false", "merge", "--no-commit", "side", check=False)
        self.assertEqual(merge.returncode, 1, "Fixture merge should conflict.")
        value = synthetic_secret()
        self.stage(value + "\n")
        self.commit("merge resolution")
        self.stage("Safe text\n")
        self.commit()
        self.assert_detected(value, mode="history")

    def test_allowlist_requires_exact_path_and_value(self) -> None:
        value = synthetic_secret()
        self.stage(value + "\n")
        self.assert_detected(value)
        with (self.repo / ".gitleaks.toml").open("a", encoding="utf-8") as config:
            config.write(
                '\n[[rules]]\nid = "github-pat"\n'
                '[[rules.allowlists]]\ndescription = "Synthetic documentation example"\n'
                "condition = \"AND\"\npaths = ['''^example\\.txt$''']\n"
                "regexTarget = \"secret\"\nregexes = ['''^" + re.escape(value) + "$''' ]\n"
            )
        self.assertEqual(self.scan().returncode, 0)
        self.git("mv", "example.txt", "elsewhere.txt")
        self.assert_detected(value)
        self.git("mv", "elsewhere.txt", "example.txt")
        neighbor = value[:-1] + ("A" if value[-1] != "A" else "B")
        self.stage(neighbor + "\n")
        self.assert_detected(neighbor)

    def test_inline_allow_comment_is_ignored(self) -> None:
        value = synthetic_secret()
        self.stage(value + " # gitleaks:allow\n")
        self.assert_detected(value)

    def test_local_ignore_file_cannot_suppress_findings(self) -> None:
        value = synthetic_secret()
        self.stage(value + "\n")
        raw = self.command(
            [
                "gitleaks",
                "git",
                "--staged",
                "--redact=100",
                "--report-format=json",
                "--report-path=-",
            ],
            check=False,
        )
        fingerprints = [row["Fingerprint"] for row in json.loads(raw.stdout)]
        (self.repo / ".gitleaksignore").write_text("\n".join(fingerprints) + "\n", encoding="utf-8")
        result = self.scan()
        self.assertEqual(result.returncode, 2)
        self.assert_redacted(result, value)

    def test_control_characters_and_html_in_paths_are_escaped(self) -> None:
        value = synthetic_secret()
        self.stage(value + "\n", "odd\n<script>.txt")
        result = self.scan()
        self.assertEqual(result.returncode, 1)
        self.assert_redacted(result, value)
        self.assertTrue("\\n" in result.stdout)
        summary = (self.directory / "summary.txt").read_text()
        self.assertTrue("<script>" not in summary)

    def test_installed_hook_blocks_initial_commit(self) -> None:
        tools = self.repo / "devtools"
        tools.mkdir()
        shutil.copyfile(WRAPPER, tools / "secret_scan.py")
        shutil.copyfile(ROOT / ".pre-commit-config.yaml", self.repo / ".pre-commit-config.yaml")
        self.git("add", ".gitleaks.toml", ".pre-commit-config.yaml", "devtools")
        self.command([sys.executable, "-m", "pre_commit", "install"])
        # A regular git commit need not run inside an activated Python environment.
        scanner = shutil.which("gitleaks", path=self.environment["PATH"])
        self.assertTrue(scanner is not None, "Gitleaks is required for scanner tests.")
        self.environment["PATH"] = str(Path(str(scanner)).parent) + os.pathsep + os.defpath
        value = synthetic_secret()
        self.stage(value + "\n")
        result = self.git("-c", "commit.gpgsign=false", "commit", "-qm", "blocked", check=False)
        self.assertEqual(result.returncode, 1, "Installed hook failed to reject a secret.")
        self.assert_redacted(result, value)
        self.assertTrue(self.git("rev-parse", "--verify", "HEAD", check=False).returncode != 0)
        self.stage("Safe text\n")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "clean")

    def test_shallow_history_is_rejected(self) -> None:
        self.stage("Safe text\n")
        self.commit()
        clone = self.directory / "shallow"
        self.command(["git", "clone", "-q", "--depth=1", self.repo.as_uri(), str(clone)])
        self.assertEqual(self.scan("history", cwd=clone).returncode, 2)

    def test_malformed_configuration_does_not_echo_values(self) -> None:
        value = synthetic_secret()
        (self.repo / ".gitleaks.toml").write_text("[" + value, encoding="utf-8")
        result = self.scan()
        self.assertEqual(result.returncode, 2)
        self.assert_redacted(result, value)

    def test_wrong_version_does_not_echo_output(self) -> None:
        value = synthetic_secret()
        self.stub_scanner("", version=value)
        result = self.scan()
        self.assertEqual(result.returncode, 2)
        self.assert_redacted(result, value)

    def test_missing_scanner_is_an_error(self) -> None:
        binaries = self.directory / "missing"
        binaries.mkdir()
        git = shutil.which("git")
        self.assertTrue(git is not None, "Git is required for scanner tests.")
        (binaries / "git").symlink_to(str(git))
        self.environment["PATH"] = str(binaries)
        self.assertEqual(self.scan().returncode, 2)

    def test_invalid_and_partial_reports_fail_closed(self) -> None:
        value = synthetic_secret()
        programs = (
            f"print({value!r})\n",
            "print('{}')\n",
            "print('[]')\nsys.exit(10)\n",
            f"print('null')\nprint({value!r}, file=sys.stderr)\nsys.exit(1)\n",
            f"print('null')\nprint({value!r}, file=sys.stderr)\n",
        )
        for index, program in enumerate(programs):
            with self.subTest(case=index):
                self.stub_scanner(program)
                result = self.scan()
                self.assertEqual(result.returncode, 2)
                self.assert_redacted(result, value)


class SecretScanBoundaryTests(unittest.TestCase):
    def test_timeout_and_launch_errors_withhold_details(self) -> None:
        value = synthetic_secret()
        errors = (
            subprocess.TimeoutExpired("fixture", 1, output=value, stderr=value),
            FileNotFoundError(value),
        )
        for index, error in enumerate(errors):
            with self.subTest(case=index), patch.object(subprocess, "run", side_effect=error):
                try:
                    secret_scan.run_private(["fixture"])
                except secret_scan.ScanError as caught:
                    self.assertTrue(value not in str(caught), "Fixture value was exposed.")
                else:
                    self.fail("Execution error did not fail closed.")

    def test_invalid_finding_locations_fail_closed(self) -> None:
        for candidate in (None, {}, {"File": "../outside", "StartLine": 1, "RuleID": "rule"}):
            with self.assertRaises(secret_scan.ScanError):
                secret_scan.sanitize_finding(candidate)

    def test_main_publishes_safe_error_on_timeout(self) -> None:
        with (
            patch.object(secret_scan, "repository_root", return_value=ROOT),
            patch.object(
                secret_scan, "scan", side_effect=secret_scan.ScanError("Secret scan timed out.")
            ),
            patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": ""}),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            code = secret_scan.main(["history"])
        self.assertEqual(code, 2)
        self.assertTrue("timed out" in output.getvalue())

    def test_required_ci_rejects_missing_or_unsuccessful_secret_job(self) -> None:
        self.assertTrue("secrets" in REQUIRED_JOBS)
        results = {name: {"result": "success"} for name in REQUIRED_JOBS}
        with (
            patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": ""}),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            required_ci(json.dumps(results))
            for status in ("failure", "skipped", "cancelled", "missing"):
                with self.subTest(status=status):
                    changed = {**results, "secrets": {"result": status}}
                    with self.assertRaises(ValueError):
                        required_ci(json.dumps(changed))
            del results["secrets"]
            with self.assertRaises(ValueError):
                required_ci(json.dumps(results))


if __name__ == "__main__":
    unittest.main()
