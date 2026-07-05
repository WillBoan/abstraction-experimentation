"""Command-line interface for arc-lab.

Examples
--------
    arc-lab datasets                      # list available datasets
    arc-lab show 007bbfb7 --dataset arc1-train --save task.png
    arc-lab eval dsl --dataset arc1-eval  # score the DSL solver on ARC-1 eval
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import typer

from arc_lab.core.dataset import DATASETS, load_dataset
from arc_lab.eval.runner import run
from arc_lab.solvers import REGISTRY, make_solver

app = typer.Typer(add_completion=False, help="ARC-AGI experimentation sandbox.")

#: Logger subtree the search strategies emit their code-level trace under.
_SEARCH_LOGGER = "arc_lab.solvers.dsl"
_LOG_FORMAT = "%(name)s %(levelname)s %(message)s"


def _configure_logging(verbosity: int) -> None:
    """Enable search tracing on stderr. ``ARC_LAB_LOG`` overrides the ``-v`` count.

    Off by default (no handler installed, so tracing costs nothing). ``-v`` shows
    INFO per-strategy summaries; ``-vv`` shows the DEBUG per-candidate trace. Only
    the ``arc_lab.solvers.dsl`` subtree is lowered, so third-party loggers stay quiet.
    """
    env = os.environ.get("ARC_LAB_LOG")
    if env:
        level = logging.getLevelNamesMapping().get(env.upper(), logging.INFO)
    elif verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.INFO
    else:
        return
    logging.basicConfig(level=logging.WARNING, format=_LOG_FORMAT, stream=sys.stderr)
    logging.getLogger(_SEARCH_LOGGER).setLevel(level)


@app.callback()
def main(
    verbose: int = typer.Option(
        0,
        "--verbose",
        "-v",
        count=True,
        help="-v: INFO search summaries, -vv: DEBUG per-candidate trace (or set ARC_LAB_LOG).",
    ),
) -> None:
    """ARC-AGI experimentation sandbox."""
    _configure_logging(verbose)


@app.command()
def datasets() -> None:
    """List the available datasets and their task counts."""
    for name in sorted(DATASETS):
        try:
            ds = load_dataset(name)
            typer.echo(f"{name:12s} {len(ds):>4d} tasks")
        except FileNotFoundError:
            typer.echo(f"{name:12s} (missing — run: git submodule update --init --recursive)")


@app.command()
def solvers() -> None:
    """List the registered solvers."""
    for name in sorted(REGISTRY):
        typer.echo(name)


@app.command()
def show(
    task_id: str = typer.Argument(..., help="Task id, e.g. 007bbfb7"),
    dataset: str = typer.Option("arc1-train", help="Dataset name."),
    save: Path | None = typer.Option(None, help="Save the render to this PNG path."),
    display: bool = typer.Option(False, "--show", help="Open an interactive window."),
) -> None:
    """Render a task's train and test pairs."""
    from arc_lab.viz import render_task

    ds = load_dataset(dataset)
    task = ds.get(task_id)
    out = save or Path(f"{task_id}.png")
    render_task(task, save=None if display else out, show=display)
    if not display:
        typer.echo(f"wrote {out}")


@app.command()
def eval(
    solver: str = typer.Argument(..., help=f"Solver name: {', '.join(sorted(REGISTRY))}"),
    dataset: str = typer.Option("arc1-eval", help="Dataset name."),
    limit: int | None = typer.Option(None, help="Only run the first N tasks."),
) -> None:
    """Run a solver over a dataset and print the score."""
    ds = load_dataset(dataset, limit=limit)
    solver_obj = make_solver(solver)
    typer.echo(f"Running {solver_obj.name} on {ds.name} ({len(ds)} tasks)...")
    report = run(solver_obj, ds, progress=True)
    typer.echo(report.summary())


if __name__ == "__main__":  # pragma: no cover
    app()
