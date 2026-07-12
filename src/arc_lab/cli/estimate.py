"""``arc-lab estimate <config> --corpus <c>`` — a worst-case search-cost ceiling, no execution."""

from __future__ import annotations

import typer

from arc_lab.program_search.execution.estimate_cost import estimate_cost
from arc_lab.program_search.execution.model.run_spec import RunSpec

from ._config import resolve_config_arg
from ._corpora import load_corpus


def estimate(
    config: str = typer.Argument(..., help="Config preset name or a JSON config file."),
    corpus: str = typer.Option(..., help="Corpus: dataset, testbed, or testbed:split."),
    set_: list[str] = typer.Option(
        [], "--set", help="Override a Config field by dotted path, e.g. budget.max_depth=4."
    ),
) -> None:
    """Print a worst-case ``considered`` ceiling for a RunSpec, without running the search."""
    preset = resolve_config_arg(config, set_)
    loaded = load_corpus(corpus)
    result = estimate_cost(RunSpec(config=preset, corpus=loaded))
    typer.echo(
        f"{config} on {loaded.name} ({len(loaded)} tasks): "
        f"considered ceiling total={result.total_considered_ceiling:,}"
    )
    worst = result.worst_task
    if worst is not None:
        typer.echo(f"  worst task: {worst.task_id} ceiling={worst.total_considered_ceiling:,}")
    for flag in result.flags:
        typer.echo(f"  ! {flag}")
