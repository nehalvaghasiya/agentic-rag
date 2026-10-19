"""Generate or verify the versioned API contract without starting application services."""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from devtools.ci import ROOT

ARTIFACTS = (
    Path("contracts/openapi.json"),
    Path("src/frontend/src/api/generated/schema.d.ts"),
)


def export_schema() -> dict:
    """Use validated defaults, bypassing external settings sources and lifespan."""
    from backend.config import Settings
    from backend.main import create_app

    # Construction only supplies known defaults; create_app revalidates the snapshot
    # using init-only sources. Neither process environment nor .env is consulted.
    return create_app(Settings.model_construct()).openapi()


def generate(destination: Path) -> None:
    schema_path, types_path = (destination / name for name in ARTIFACTS)
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    types_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(json.dumps(export_schema(), indent=2, sort_keys=True) + "\n")
    subprocess.run(
        [
            "node",
            str(ROOT / "src/frontend/scripts/generate-contracts.mjs"),
            str(schema_path),
            str(types_path),
        ],
        cwd=ROOT,
        check=True,
    )


def compare(expected: Path, actual: Path) -> bool:
    """Report missing, extra, or edited generated artifacts without modifying them."""
    names = set(ARTIFACTS)
    for base in (expected, actual):
        directory = base / "src/frontend/src/api/generated"
        if directory.exists():
            names.update(p.relative_to(base) for p in directory.rglob("*") if p.is_file())
    matches = True
    for name in sorted(names):
        left, right = expected / name, actual / name
        if left.is_file() and right.is_file() and left.read_bytes() == right.read_bytes():
            continue
        matches = False
        print(f"Contract drift: {name}")
        print(
            "".join(
                difflib.unified_diff(
                    left.read_text().splitlines(keepends=True) if left.is_file() else [],
                    right.read_text().splitlines(keepends=True) if right.is_file() else [],
                    fromfile=f"committed/{name}",
                    tofile=f"generated/{name}",
                )
            ),
            end="",
        )
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "check"))
    args = parser.parse_args()
    try:
        if args.command == "generate":
            generate(ROOT)
        else:
            with TemporaryDirectory(prefix="rag-contracts-") as directory:
                destination = Path(directory)
                generate(destination)
                if not compare(ROOT, destination):
                    print("Run: uv run --no-sync python -m devtools.contracts generate")
                    return 1
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"FAIL: contracts: {error}")
        return 1
    print(f"PASS: contracts {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
