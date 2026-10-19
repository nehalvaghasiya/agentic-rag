"""Run required check families locally in an already prepared environment."""

from __future__ import annotations

import json
import platform
import subprocess
import sys

from devtools.ci import ROOT, python_matrix


def main() -> int:
    stage = "tool versions"
    try:
        supported = {row["label"] for row in python_matrix()["include"]}
        if ".".join(platform.python_version_tuple()[:2]) not in supported:
            raise ValueError(f"Python must be one of {sorted(supported)}")
        package = json.loads((ROOT / "src/frontend/package.json").read_text())
        expected = {
            "uv": "uv 0.12.1 ",
            "node": "v" + (ROOT / ".nvmrc").read_text().strip(),
            "npm": package["packageManager"].removeprefix("npm@"),
            "actionlint": "1.7.12\n",
            "shellcheck": "ShellCheck - shell script analysis tool\nversion: 0.11.0\n",
        }
        for tool, version in expected.items():
            flag = "-version" if tool == "actionlint" else "--version"
            actual = subprocess.check_output([tool, flag], text=True, cwd=ROOT)
            if not actual.startswith(version):
                raise ValueError(f"Expected {tool} {version.strip()}, got {actual.strip()}")
        subprocess.run(["docker", "buildx", "version"], cwd=ROOT, check=True)
        frontend = ROOT / "src/frontend"
        stages = [
            ("source layout", [sys.executable, "-m", "devtools.ci", "layout"], ROOT),
            ("workflow lint", ["actionlint", "-shellcheck", "shellcheck"], ROOT),
            ("lock freshness", ["uv", "lock", "--check"], ROOT),
            (
                "frontend lock freshness",
                [sys.executable, "-m", "devtools.ci", "frontend-lock"],
                ROOT,
            ),
            ("backend quality", [sys.executable, "-m", "devtools.lint"], ROOT),
            ("backend tests", [sys.executable, "-m", "pytest", "-p", "no:sugar"], ROOT),
            ("frontend lint", ["npm", "run", "lint"], frontend),
            ("API contracts", [sys.executable, "-m", "devtools.contracts", "check"], ROOT),
            ("frontend types", ["npm", "run", "type-check"], frontend),
            ("frontend tests", ["npm", "test"], frontend),
            ("frontend build", ["npm", "run", "build"], frontend),
            ("browser journeys", ["npm", "run", "test:e2e"], frontend),
            ("package matrix", [sys.executable, "-m", "devtools.ci", "package"], ROOT),
        ]
        for stage, command, directory in stages:
            print(f"\nChecking {stage}: {' '.join(command)}", flush=True)
            subprocess.run(command, cwd=directory, check=True)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"\nFAIL: {stage}: {error}", flush=True)
        return 1
    except KeyboardInterrupt:
        print(f"\nCancelled during {stage}", flush=True)
        return 130
    print("\nPASS: all local check families", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
