"""``arc-lab run-ladder``: execute a registered Ladder and print its report.

Thin wrapper (all behavior lives in ``program_search/ladders/``): resolve a name from the
registry, render + lint the spec, execute the climb + oracle chain + off-chain run, print the
report JSON. Mirrors ``run-study``.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.report import create_ladder_report
from arc_lab.program_search.ladders.run import run_ladder


def run_ladder_command(
    name: str = typer.Argument(..., help="Registered ladder name (ladders/registry)."),
    out: Path | None = typer.Option(None, help="Also write the report JSON to this path."),
) -> None:
    try:
        spec = make_ladder(name)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(spec.render())
    if not spec.lint().ok:
        typer.echo("WARNING: ladder lint has errors (see the render above); running anyway.")
    typer.echo(f"running ladder {name}...")
    report = create_ladder_report(run_ladder(spec, runs_root=None))
    payload = json.dumps(report, indent=2, sort_keys=True)
    if out is not None:
        out.write_text(payload + "\n", encoding="utf-8")
        typer.echo(f"wrote {out}")
    typer.echo(payload)
