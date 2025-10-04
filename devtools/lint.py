import subprocess
import sys

from funlog import log_calls
from rich import get_console, reconfigure
from rich import print as rprint

# Update as needed.
SRC_PATHS = ["src", "devtools"]
DOC_PATHS = ["README.md"]


reconfigure(emoji=not get_console().options.legacy_windows)  # No emojis on legacy windows.


def main():
    rprint()

    errcount = 0
    errcount += run(["codespell", "--write-changes", *SRC_PATHS, *DOC_PATHS])
    errcount += run(["ruff", "check", "--fix", *SRC_PATHS])
    errcount += run(["ruff", "format", *SRC_PATHS])
    errcount += run_basedpyright()

    rprint()

    if errcount != 0:
        rprint(f"[bold red]:x: Lint failed with {errcount} errors.[/bold red]")
    else:
        rprint("[bold green]:white_check_mark: Lint passed![/bold green]")
    rprint()

    return errcount


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

    return errcount


@log_calls(level="warning", show_timing_only=True)
def run_basedpyright() -> int:
    """Run basedpyright and only fail if there are actual errors, not warnings."""
    cmd = ["basedpyright", "--level", "error", "--stats", "src", "devtools"]
    rprint()
    rprint(f"[bold green]>> {' '.join(cmd)}[/bold green]")

    errcount = 0
    try:
        result = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
        )

        # Print the output
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)

        # Parse the output to check for actual errors
        # Look for lines like "X errors, Y warnings, Z notes"
        output_text = result.stdout + result.stderr
        for line in output_text.split("\n"):
            # Match pattern like "0 errors, 264 warnings, 0 notes" or "5 errors, 10 warnings"
            if "error" in line.lower():
                parts = line.split()
                for i, part in enumerate(parts):
                    if "error" in part.lower():
                        # Try to get the number before "errors" or "error"
                        try:
                            if i > 0:
                                error_count = int(parts[i - 1])
                                if error_count > 0:
                                    errcount = 1
                                    rprint(
                                        f"[bold red]Found {error_count} type error(s)[/bold red]"
                                    )
                                else:
                                    rprint(
                                        "[bold green]No type errors found (0 errors)[/bold green]"
                                    )
                        except (ValueError, IndexError):
                            pass
                        break

        # If we didn't find an error count line, but found no errors pattern, success
        if errcount == 0 and "0 error" in output_text.lower():
            rprint("[bold green]Type checking passed with 0 errors[/bold green]")

    except KeyboardInterrupt:
        rprint("[yellow]Keyboard interrupt - Cancelled[/yellow]")
        errcount = 1
    except Exception as e:
        rprint(f"[bold red]Error running basedpyright: {e}[/bold red]")
        errcount = 1

    return errcount


if __name__ == "__main__":
    exit(main())
