"""``arc-lab show <task_id>`` — render a task's train and test pairs."""

from __future__ import annotations

from pathlib import Path

import typer

from arc_lab.core.dataset import load_dataset


def show(
    task_id: str = typer.Argument(..., help="Task id, e.g. 007bbfb7"),
    dataset: str = typer.Option("arc1-train", help="Dataset name."),
    save: Path | None = typer.Option(None, help="Save the render to this PNG path."),
    display: bool = typer.Option(False, "--show", help="Open an interactive window."),
) -> None:
    """Render a task's train and test pairs."""
    from arc_lab.viz import render_task

    corpus = load_dataset(dataset)
    task = corpus.get(task_id)
    out = save or Path(f"{task_id}.png")
    render_task(task, save=None if display else out, show=display)
    if not display:
        typer.echo(f"wrote {out}")
