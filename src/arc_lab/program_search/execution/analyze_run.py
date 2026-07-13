"""``analyze_run``: read-side analysis of a completed recorded run (EXECUTION.md).

Pure read over the run's artifacts — never executes. The summary aggregates what the
artifacts already observe (solve counts, search effort, found programs, learn
trajectory); derived ratios (compression, speedup) are computed here from stored
observations, matching the discipline that a run artifact stores observations only.
"""

from __future__ import annotations

from pathlib import Path

from arc_lab.program_search.analysis.capabilities import group_outcomes
from arc_lab.program_search.substrate.library import Library

from .execute import DEFAULT_RUNS_ROOT, merge_outcome_stats
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
        library = record.config_library()
        programs: dict[str, list[str]] = {}
        effort: dict[str, int] = {}
        outcomes_by_task: dict[str, dict[str, int]] = {}
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
            if isinstance(stats, dict) and isinstance(stats.get("outcomes"), dict):
                outcomes_by_task[task_id] = stats["outcomes"]
        summary["programs"] = programs
        summary["considered_by_task"] = effort
        summary["outcomes_by_task"] = outcomes_by_task
        by_key_total = results.get("by_key_total")
        if isinstance(by_key_total, dict):
            summary["by_category"] = group_outcomes(by_key_total, by="category", library=library)
            summary["by_provenance"] = group_outcomes(
                by_key_total, by="provenance", library=library
            )
    else:  # a LEARN run: the per-iteration trajectory
        trajectory: list[dict[str, object]] = []
        library = record.config_library()  # the seed library, before any sleep grows it
        for row in record.trace_rows():
            trajectory.append(_trajectory_row(row, library))
            if row.get("phase") == "sleep":
                library_data = row.get("library")
                if isinstance(library_data, dict):
                    library = Library.from_dict(library_data)  # in force for the *next* wake
        summary["trajectory"] = trajectory
    return summary


def _trajectory_row(row: dict[str, object], library: Library) -> dict[str, object]:
    """One LEARN trace row's trajectory entry: the tracked top-level keys, plus — for a wake row
    — the wake's per-task stats merged into one outcomes/by-key/category/provenance total (e.g.
    to see whether a primitive sleep just minted gets used in the very next wake). ``library`` is
    the library that was *in force during that wake* — the seed library for wake 0, or whatever
    the preceding sleep row grew it to."""
    entry = {
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
    stats = row.get("stats")
    if row.get("phase") == "wake" and isinstance(stats, dict):
        outcomes_total, by_key_total = merge_outcome_stats(
            task_stats for task_stats in stats.values() if isinstance(task_stats, dict)
        )
        entry["outcomes_total"] = outcomes_total
        entry["by_key_total"] = by_key_total
        entry["by_category"] = group_outcomes(by_key_total, by="category", library=library)
        entry["by_provenance"] = group_outcomes(by_key_total, by="provenance", library=library)
    return entry
