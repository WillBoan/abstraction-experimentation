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
from arc_lab.program_search.ladders.probe import PROBE_CORPUS_PREFIX


def list_runs(
    directory: Path | None = typer.Option(None, "--dir", help="Runs directory (default runs/)."),
    probes: bool = typer.Option(
        False,
        "--probes",
        help="Include design-time PROBE cells. Hidden by default: a probe run is one rung x one "
        "library x one task, so an authoring session makes dozens -- mostly for ladders that never "
        "ship -- and this listing is meant to be a ledger of experiment results.",
    ),
) -> None:
    """One line per completed recorded run: id, corpus, kind, headline numbers."""
    root = DEFAULT_RUNS_ROOT if directory is None else directory
    if not root.is_dir():
        typer.echo(f"no runs under {root}")
        return
    rows = []
    hidden = 0
    for run_dir in iter_run_dirs(root):
        runspec_path = run_dir / RUNSPEC_FILENAME
        spec = json.loads(runspec_path.read_text(encoding="utf-8"))
        record = RunRecord(run_id=spec["run_id"], run_dir=run_dir)
        if not record.completed:
            continue
        # Probe cells ARE ordinary recorded runs (that is the point -- they cache and resume like
        # anything else); they are simply not results, so the default listing filters them by their
        # corpus namespace rather than by a second storage location.
        if str(spec.get("corpus_name", "")).startswith(PROBE_CORPUS_PREFIX):
            hidden += 1
            if not probes:
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
    if hidden and not probes:
        typer.echo(f"\n({hidden} probe cell(s) hidden -- `arc-lab runs --probes` to include them)")
