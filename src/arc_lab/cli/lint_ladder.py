"""``arc-lab lint-ladder``: check a `.ladder` source without running anything.

The authoring loop. Unlike ``run-ladder`` (which lints and then executes the whole climb), this
only reads: it parses and resolves the file -- every load-time check, with line numbers -- then
generates the corpus **in memory** and reports the static lint. So a *draft* ladder can be checked
before its testbed exists, and the loop is edit -> lint -> edit rather than edit -> taskgen -> run.

Exits non-zero when the lint has errors, so it works in a pre-commit hook or a script.
"""

from __future__ import annotations

import typer

from arc_lab.program_search.ladders.lang.errors import LadderFormatError
from arc_lab.program_search.ladders.lang.load import draft_spec
from arc_lab.program_search.ladders.registry import ladder_paths, load_ladder


def lint_ladder_command(
    name: str = typer.Argument(
        None, help="Ladder name (its `.ladder` filename stem); omit to lint every ladder."
    ),
    quiet: bool = typer.Option(
        False, "--quiet", "-q", help="Only report findings, not the full rendered spec."
    ),
) -> None:
    names = sorted(ladder_paths()) if name is None else [name]
    failures = 0
    for ladder_name in names:
        failures += _lint_one(ladder_name, quiet=quiet or name is None)
    if name is None:
        typer.echo(f"\n{len(names) - failures}/{len(names)} ladders lint clean")
    if failures:
        raise typer.Exit(code=1)


def _lint_one(name: str, *, quiet: bool) -> int:
    """Lint one ladder; return 1 if it has errors (or could not be loaded), else 0."""
    try:
        spec = draft_spec(load_ladder(name))
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except LadderFormatError as exc:  # a load error: the file cannot mean anything yet
        typer.echo(f"{name}: LOAD FAILED -- {exc}")
        return 1

    shape = spec.lint()
    errors = [f for f in shape.findings if not f.ok and f.severity == "error"]
    warnings = [f for f in shape.findings if not f.ok and f.severity == "warn"]
    if not quiet:
        typer.echo(spec.render())
        typer.echo("")
    verdict = "OK" if shape.ok else "FAILED"
    typer.echo(
        f"{name}: {verdict} -- {len(shape.findings)} checks "
        f"({len(errors)} errors, {len(warnings)} warnings)"
    )
    for finding in errors:
        typer.echo(f"  ERROR {finding.check}: {finding.detail}")
    for finding in warnings:
        typer.echo(f"  warn  {finding.check}: {finding.detail}")
    return 0 if shape.ok else 1
