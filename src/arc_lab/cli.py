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

from arc_lab.core.dataset import DATASETS, Dataset, load_dataset
from arc_lab.eval.runner import run
from arc_lab.solvers import REGISTRY, make_solver
from arc_lab.solvers.dsl.trace import TaskIdFilter

app = typer.Typer(add_completion=False, help="ARC-AGI experimentation sandbox.")

#: Logger subtree the search strategies emit their code-level trace under.
_SEARCH_LOGGER = "arc_lab.solvers.dsl"
#: ``task_id`` is supplied by :class:`TaskIdFilter`; it reads ``-`` outside a solve.
_LOG_FORMAT = "%(task_id)s %(name)s %(levelname)s %(message)s"


def _configure_logging(verbosity: int) -> None:
    """Enable search tracing on stderr. ``ARC_LAB_LOG`` overrides the ``-v`` count.

    Off by default (no handler installed, so tracing costs nothing). ``-v`` shows
    INFO per-strategy summaries; ``-vv`` shows the DEBUG per-candidate trace. Only
    the ``arc_lab.solvers.dsl`` subtree is lowered, so third-party loggers stay quiet.
    Every line is prefixed with the task id (via :class:`TaskIdFilter`) so a
    multi-task trace can be grepped by task.

    # TODO(trace-as-data, optional): for offline search-space analysis — dedup
    # ratios, behaviours-per-task, depth-to-solve — add a `--trace-file run.jsonl`
    # option here that installs a second handler emitting one JSON object per event
    # (task_id, event, program, sig, depth). Worth doing once you start *studying*
    # the search (e.g. to mine observational-equivalence collisions for library
    # learning) rather than debugging it; until then the console trace suffices.
    # `structlog` (bound context + JSON renderer) would be the clean way to do both
    # this and the task-id prefix above, at the cost of one dependency.
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
    for handler in logging.getLogger().handlers:
        if not any(isinstance(existing, TaskIdFilter) for existing in handler.filters):
            handler.addFilter(TaskIdFilter())
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
    task: str | None = typer.Option(
        None, "--task", help="Run only this task id (ignores --limit). Ideal with -vv."
    ),
) -> None:
    """Run a solver over a dataset and print the score."""
    # A single --task overrides --limit: load the whole dataset, then narrow to it.
    ds = load_dataset(dataset, limit=None if task else limit)
    if task is not None:
        try:
            ds = Dataset(name=ds.name, tasks=(ds.get(task),))
        except KeyError as exc:
            raise typer.BadParameter(str(exc)) from exc
    solver_obj = make_solver(solver)
    typer.echo(f"Running {solver_obj.name} on {ds.name} ({len(ds)} tasks)...")
    report = run(solver_obj, ds, progress=True)
    typer.echo(report.summary())


@app.command()
def analyze(
    solver: str = typer.Argument(..., help=f"Program-search solver: {', '.join(sorted(REGISTRY))}"),
    dataset: str = typer.Option("arc1-train", help="Dataset name."),
    out: Path = typer.Option(Path("runs"), help="Directory to write run artifacts under."),
    limit: int | None = typer.Option(None, help="Only run the first N tasks."),
    force: bool = typer.Option(False, "--force", help="Ignore any cached run and recompute."),
) -> None:
    """Run a program-search solver and write a durable run artifact (programs + metrics).

    Unlike ``eval`` (solver-agnostic, solve-count only), this introspects the DSL solver
    to record the program found per task and the search effort spent, then computes the
    run's description length. Runs are content-addressed, cached, and resumable.
    """
    from arc_lab.solvers.dsl.analysis import analyze as run_analysis
    from arc_lab.solvers.dsl.solver import ProgramSearchSolver

    solver_obj = make_solver(solver)
    if not isinstance(solver_obj, ProgramSearchSolver):
        raise typer.BadParameter(f"{solver!r} is not a program-search solver (analyze needs one)")
    ds = load_dataset(dataset, limit=limit)
    typer.echo(f"Analyzing {solver_obj.name} on {ds.name} ({len(ds)} tasks)...")
    summary, run_dir = run_analysis(solver_obj, ds, out_dir=out, force=force, progress=True)
    typer.echo(summary.summary_line())
    typer.echo(f"wrote {run_dir}")


@app.command()
def learn(
    experiment: str = typer.Argument(..., help="Experiment name, e.g. e1-rot90"),
    testbeds: Path = typer.Option(Path("testbeds"), help="Where to write generated testbeds."),
    runs: Path = typer.Option(Path("runs"), help="Where to write run artifacts."),
) -> None:
    """Run an abstraction-formation experiment: generate a testbed, learn a library, report.

    The system learns blind on the train split; the hand-authored target abstractions are
    used only to *observe* (behavioral checker + library 3), never to guide learning.
    """
    from arc_lab.solvers.dsl.learn.experiments import make_experiment, run_experiment

    try:
        exp = make_experiment(experiment)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Running experiment {exp.name}...")
    report = run_experiment(exp, testbeds_root=testbeds, runs_root=runs)
    for line in report.summary_lines():
        typer.echo(line)


if __name__ == "__main__":  # pragma: no cover
    app()
