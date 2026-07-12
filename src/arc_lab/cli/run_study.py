"""``arc-lab run-study <name>`` — execute a registered study and print its report."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from arc_lab.program_search.execution.run_study import create_study_report, run_study
from arc_lab.program_search.execution.studies import make_study


def run_study_command(
    name: str = typer.Argument(..., help="Registered study name (studies.py::STUDIES)."),
    out: Path | None = typer.Option(None, help="Also write the report JSON to this path."),
) -> None:
    """Execute the study grid (cache hits are free) and print the report JSON."""
    try:
        spec = make_study(name)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"running study {name}...")
    result = run_study(spec, runs_root=None)
    report = create_study_report(result)
    payload = json.dumps(report, indent=2, sort_keys=True)
    if out is not None:
        out.write_text(payload + "\n", encoding="utf-8")
        typer.echo(f"wrote {out}")
    typer.echo(payload)
