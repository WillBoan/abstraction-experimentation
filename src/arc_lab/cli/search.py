"""``arc-lab search <config> --corpus <c>`` — execute one SEARCH recorded run."""

from __future__ import annotations

import typer

from arc_lab.program_search.execution.run_search import run_search

from ._config import resolve_config_arg
from ._corpora import load_corpus


def search(
    config: str = typer.Argument(..., help="Config preset name or a JSON config file."),
    corpus: str = typer.Option(..., help="Corpus: dataset, testbed, or testbed:split."),
    set_: list[str] = typer.Option(
        [], "--set", help="Override a Config field by dotted path, e.g. budget.max_depth=4."
    ),
) -> None:
    """Execute (or serve from cache) one SEARCH recorded run."""
    preset = resolve_config_arg(config, set_)
    loaded = load_corpus(corpus)
    typer.echo(f"searching {config} on {loaded.name} ({len(loaded)} tasks)...")
    record = run_search(preset, loaded, runs_root=None)
    results = record.results()
    typer.echo(
        f"run {record.run_id}: solved {results.get('solved')}/{results.get('task_count')} "
        f"considered={results.get('considered_total')}"
    )
    typer.echo(f"recorded at {record.run_dir}")
