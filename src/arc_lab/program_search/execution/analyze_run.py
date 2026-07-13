"""``analyze_run``: read-side analysis of a completed recorded run (EXECUTION.md).

Pure read over the run's artifacts — never executes. The summary aggregates what the
artifacts already observe (solve counts, search effort, found programs, learn
trajectory); derived ratios (compression, speedup) are computed here from stored
observations, matching the discipline that a run artifact stores observations only.
"""

from __future__ import annotations

from pathlib import Path

from .execute import DEFAULT_RUNS_ROOT
from .model.run_record import RunRecord, find_run_dir


def analyze_run(run_id: str, *, runs_root: Path | None = None) -> dict[str, object]:
    """A structured summary of a completed run's artifacts, by ``run_id``."""
    root = DEFAULT_RUNS_ROOT if runs_root is None else runs_root
    run_dir = find_run_dir(root, run_id)
    if run_dir is None:
        raise FileNotFoundError(f"run {run_id!r} has no results.json under {root}")
    record = RunRecord(run_id=run_id, run_dir=run_dir)
    if not record.completed:
        raise FileNotFoundError(f"run {run_id!r} has no results.json under {root}")

    results = record.results()
    summary: dict[str, object] = {"run_id": run_id, "results": results}

    if "tasks" in results:  # a SEARCH run: per-task programs + effort from the trace
        programs: dict[str, list[str]] = {}
        effort: dict[str, int] = {}
        for row in record.trace_rows():
            task_id = row.get("task_id")
            if not isinstance(task_id, str):
                continue
            found = row.get("programs")
            if isinstance(found, list):
                programs[task_id] = [str(program) for program in found]
            stats = row.get("stats")
            if isinstance(stats, dict) and isinstance(stats.get("considered"), int):
                effort[task_id] = stats["considered"]
        summary["programs"] = programs
        summary["considered_by_task"] = effort
    else:  # a LEARN run: the per-iteration trajectory
        trajectory = [
            {
                key: row.get(key)
                for key in (
                    "iteration",
                    "phase",
                    "solved",
                    "considered",
                    "added",
                    "description_length",
                    "converged",
                )
            }
            for row in record.trace_rows()
        ]
        summary["trajectory"] = trajectory
    return summary
