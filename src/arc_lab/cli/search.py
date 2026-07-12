"""``arc-lab search <config> --corpus <c>`` — execute one SEARCH recorded run."""

from __future__ import annotations

import typer

from arc_lab.program_search.execution.presets import resolve_config
from arc_lab.program_search.execution.run_search import run_search

from ._corpora import load_corpus


def search(
    config: str = typer.Argument(..., help="Config preset name (see `arc-lab configs`)."),
    corpus: str = typer.Option(..., help="Corpus: dataset, testbed, or testbed:split."),
) -> None:
    """Execute (or serve from cache) one SEARCH recorded run."""
    try:
        preset = resolve_config(config)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    loaded = load_corpus(corpus)
    typer.echo(f"searching {config} on {loaded.name} ({len(loaded)} tasks)...")
    record = run_search(preset, loaded, runs_root=None)
    results = record.results()
    typer.echo(
        f"run {record.run_id}: solved {results.get('solved')}/{results.get('task_count')} "
        f"considered={results.get('considered_total')}"
    )
    typer.echo(f"recorded at {record.run_dir}")
