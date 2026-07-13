"""``arc-lab analyze-run <run_id>`` — READ-ONLY analysis of a completed recorded run."""

from __future__ import annotations

import json

import typer

from arc_lab.program_search.execution.analyze_run import analyze_run


def analyze_run_command(
    run_id: str = typer.Argument(..., help="The run id (a runs/ directory name)."),
) -> None:
    """Print a structured summary of a completed run's artifacts. Never executes."""
    try:
        summary = analyze_run(run_id, runs_root=None)
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc
    # Insertion order, not sorted: stats blocks are built in funnel order and must stay that way.
    typer.echo(json.dumps(summary, indent=2))
