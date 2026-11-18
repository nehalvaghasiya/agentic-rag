"""Print prepared GitHub issue import commands; use --apply only intentionally.

Requires GitHub CLI `gh`, authenticated repository remote and user review.
Never creates remote issues without the explicit --apply flag.
"""

import argparse
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Create actual GitHub issues")
    parser.add_argument("--repo", default=None, help="Explicit owner/repo to target")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / ".github" / "issue_blueprints"
    issues = sorted(root.glob("[0-9][0-9].md"))
    if len(issues) != 29:
        raise ValueError("Expected all 29 issue blueprints")
    if args.apply and not args.repo:
        raise ValueError("--apply requires explicit --repo owner/name")
    for path in issues:
        title = path.read_text().splitlines()[0].removeprefix("# ")
        cmd = ["gh", "issue", "create", "--title", title, "--body-file", str(path)]
        if args.repo:
            cmd.extend(["--repo", args.repo])
        if args.apply:
            subprocess.run(cmd, check=True)
        else:
            print(f"{path.stem}: {title}")
    if not args.apply:
        print(
            "Dry-run only. To create issues: python scripts/create_issues.py --apply --repo OWNER/REPO"
        )


if __name__ == "__main__":
    main()
