"""``arc-lab taskgen <generator>`` — write a committed testbed (generation, not consumption)."""

from __future__ import annotations

from pathlib import Path

import typer

from arc_lab.taskgen.generators import generate


def taskgen(
    generator: str = typer.Argument(..., help="Generator name (taskgen/generators.py)."),
    out: Path = typer.Option(Path("testbeds"), help="Root directory to write testbeds under."),
) -> None:
    """Deterministically (re)generate a synthetic testbed."""
    try:
        root = generate(generator, out)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"wrote {root}")
