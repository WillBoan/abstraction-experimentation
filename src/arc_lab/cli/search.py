"""``arc-lab search <config> --corpus <c>`` — execute one SEARCH recorded run."""

from __future__ import annotations

import typer

from arc_lab.program_search.execution.model.run_record import considered_total
from arc_lab.program_search.execution.run_search import run_search

from ._config import resolve_config_arg
from ._corpora import load_corpus
from ._trace import build_trace_spec


def search(
    config: str = typer.Argument(..., help="Config preset name or a JSON config file."),
    corpus: str = typer.Option(..., help="Corpus: dataset, testbed, or testbed:split."),
    set_: list[str] = typer.Option(
        [], "--set", help="Override a Config field by dotted path, e.g. budget.max_depth=4."
    ),
    sample: list[str] = typer.Option(
        [],
        "--sample",
        help="Reservoir sample spec 'k:mode' (mode: first_k, cheapest_k), repeatable. "
        "Default: a small first_k sampler.",
    ),
    track_all: bool = typer.Option(
        False, "--track-all", help="Capture every considered candidate to capture/<task>.jsonl."
    ),
    capture_max: int = typer.Option(
        100_000, "--capture-max", help="Cap on captured candidates per task with --track-all."
    ),
    force_recapture: bool = typer.Option(
        False,
        "--force-recapture",
        help="Re-execute an already-completed run to (re)populate tracing artifacts.",
    ),
    profile: bool = typer.Option(
        False,
        "--profile",
        help="Profile the run under cProfile; writes profile/summary.txt + stats.prof. "
        "Needs --force-recapture on an already-cached run.",
    ),
) -> None:
    """Execute (or serve from cache) one SEARCH recorded run."""
    preset = resolve_config_arg(config, set_)
    loaded = load_corpus(corpus)
    trace_spec = build_trace_spec(sample, track_all, capture_max, profile)
    typer.echo(f"searching {config} on {loaded.name} ({len(loaded)} tasks)...")
    record = run_search(
        preset, loaded, runs_root=None, trace=trace_spec, force_recapture=force_recapture
    )
    results = record.results()
    typer.echo(
        f"run {record.run_id}: solved {results.get('solved')}/{results.get('task_count')} "
        f"considered={considered_total(results)}"
    )
    typer.echo(f"recorded at {record.run_dir}")
