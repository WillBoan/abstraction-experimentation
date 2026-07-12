"""``arc-lab datasets`` — list the available datasets and their task counts."""

from __future__ import annotations

import typer

from arc_lab.core.dataset import ARC_DATASETS, load_dataset


def list_datasets() -> None:
    """List the available datasets and their task counts."""
    for name in sorted(ARC_DATASETS):
        try:
            corpus = load_dataset(name)
            typer.echo(f"{name:12s} {len(corpus):>4d} tasks")
        except FileNotFoundError:
            typer.echo(f"{name:12s} (missing — run: git submodule update --init --recursive)")
