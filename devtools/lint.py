import argparse
import subprocess
from collections.abc import Sequence

from funlog import log_calls
from rich import get_console, reconfigure
from rich import print as rprint

PYTHON_PATHS = ["backend", "devtools"]
SPELLCHECK_PATHS = [*PYTHON_PATHS, "README.md"]


reconfigure(emoji=not get_console().options.legacy_windows)  # No emojis on legacy windows.


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check backend code quality.")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="apply spelling, lint, and formatting fixes before type-checking",
    )
    args = parser.parse_args(argv)

    rprint()

    commands = [
        [
            "codespell",
            *(["--write-changes"] if args.fix else []),
            *SPELLCHECK_PATHS,
        ],
        ["ruff", "check", *(["--fix"] if args.fix else []), *PYTHON_PATHS],
        ["ruff", "format", *([] if args.fix else ["--check"]), *PYTHON_PATHS],
        ["basedpyright", "--stats"],
    ]
    failure_count = sum(run(command) for command in commands)

    rprint()

    if failure_count:
        rprint(f"[bold red]:x: Quality checks failed in {failure_count} stage(s).[/bold red]")
    else:
        rprint("[bold green]:white_check_mark: Quality checks passed![/bold green]")
    rprint()

    return failure_count


@log_calls(level="warning", show_timing_only=True)
def run(cmd: list[str]) -> int:
    rprint()
    rprint(f"[bold green]>> {' '.join(cmd)}[/bold green]")
    errcount = 0
    try:
        subprocess.run(cmd, text=True, check=True)
    except KeyboardInterrupt:
        rprint("[yellow]Keyboard interrupt - Cancelled[/yellow]")
        errcount = 1
    except subprocess.CalledProcessError as e:
        rprint(f"[bold red]Error: {e}[/bold red]")
        errcount = 1
    except OSError as e:
        rprint(f"[bold red]Unable to run command: {e}[/bold red]")
        errcount = 1

    return errcount


if __name__ == "__main__":
    exit(main())
