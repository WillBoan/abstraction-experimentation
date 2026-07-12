"""``arc-lab configs`` — list the named machinery presets."""

from __future__ import annotations

import typer

from arc_lab.program_search.execution.presets import PRESETS


def list_configs() -> None:
    """One line per preset: library, engine, budget."""
    for name in sorted(PRESETS):
        config = PRESETS[name]
        budget = config.budget
        typer.echo(
            f"{name:8s} library={config.library.name:16s} "
            f"engine={type(config.search_engine).__name__:28s} "
            f"budget=(depth={budget.max_depth}, arity={budget.max_arity}, pool={budget.max_pool})"
        )
