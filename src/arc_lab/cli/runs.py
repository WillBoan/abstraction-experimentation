"""``arc-lab runs`` — list recorded run artifacts under the runs/ cache."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from arc_lab.program_search.execution.execute import DEFAULT_RUNS_ROOT
from arc_lab.program_search.execution.model.run_record import (
    RUNSPEC_FILENAME,
    RunRecord,
    considered_total,
    iter_run_dirs,
)


def list_runs(
    directory: Path | None = typer.Option(None, "--dir", help="Runs directory (default runs/)."),
) -> None:
    """One line per completed recorded run: id, corpus, kind, headline numbers."""
    root = DEFAULT_RUNS_ROOT if directory is None else directory
    if not root.is_dir():
        typer.echo(f"no runs under {root}")
        return
    rows = []
    for run_dir in iter_run_dirs(root):
        runspec_path = run_dir / RUNSPEC_FILENAME
        spec = json.loads(runspec_path.read_text(encoding="utf-8"))
        record = RunRecord(run_id=spec["run_id"], run_dir=run_dir)
        if not record.completed:
            continue
        results = record.results()
        is_learn = spec.get("config", {}).get("learn") is not None
        if is_learn:
            headline = (
                f"LEARN  iterations={results.get('iterations_run')} "
                f"added={results.get('added')} library_size={results.get('library_size')}"
            )
        else:
            headline = (
                f"SEARCH solved={results.get('solved')}/{results.get('task_count')} "
                f"considered={considered_total(results)}"
            )
        rows.append(f"{record.run_id}  {results.get('corpus_name', '?'):24s} {headline}")
    if not rows:
        typer.echo(f"no completed runs under {root}")
        return
    for row in rows:
        typer.echo(row)
