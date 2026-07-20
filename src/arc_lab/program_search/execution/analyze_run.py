"""``analyze_run``: read-side analysis of a completed recorded run (EXECUTION.md).

Pure read over the run's artifacts — never executes. The summary aggregates what the
artifacts already observe (solve counts, search effort, found programs, learn
trajectory); derived ratios (compression, speedup) are computed here from stored
observations, matching the discipline that a run artifact stores observations only.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from arc_lab.program_search.analysis.capabilities import group_outcomes
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Program

from .execute import DEFAULT_RUNS_ROOT, merge_search_stats
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
                # The trace stores programs as codec dicts (``to_dict``); decode to their readable
                # source form, matching ``execute._readable_programs`` (never ``str()`` a raw dict).
                programs[task_id] = [
                    str(Program.from_dict(program))
                    if isinstance(program, Mapping)
                    else str(program)
                    for program in found
                ]
            total = _stats_total(row.get("search_stats"))
            if total is not None:
                considered = total.get("considered")
                if isinstance(considered, int):
                    effort[task_id] = considered
                outcomes_by_task[task_id] = {
                    name: count
                    for name, count in total.items()
                    if name != "considered" and isinstance(count, int)
                }
        summary["programs"] = programs
        summary["considered_by_task"] = effort
        summary["outcomes_by_task"] = outcomes_by_task
        search_stats = results.get("search_stats")
        by_primitive = search_stats.get("by_primitive") if isinstance(search_stats, dict) else None
        if isinstance(by_primitive, dict):
            summary["by_category"] = group_outcomes(by_primitive, by="category", library=library)
            summary["by_provenance"] = group_outcomes(
                by_primitive, by="provenance", library=library
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


def _stats_total(search_stats: object) -> dict[str, object] | None:
    """The ``total`` block of a per-task ``search_stats`` mapping, or ``None``."""
    if isinstance(search_stats, dict):
        total = search_stats.get("total")
        if isinstance(total, dict):
            return total
    return None


def _trajectory_row(row: dict[str, object], library: Library) -> dict[str, object]:
    """One LEARN trace row's trajectory entry: the tracked top-level keys, plus — for a wake row
    — the wake's per-task stats merged into one search_stats/category/provenance total (e.g. to
    see whether a primitive sleep just minted gets used in the very next wake). ``library`` is the
    library that was *in force during that wake* — the seed library for wake 0, or whatever the
    preceding sleep row grew it to."""
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
    search_stats = row.get("search_stats")
    if row.get("phase") == "wake" and isinstance(search_stats, dict):
        merged = merge_search_stats(
            block for block in search_stats.values() if isinstance(block, dict)
        )
        by_primitive = merged["by_primitive"]
        assert isinstance(by_primitive, dict)
        entry["search_stats"] = merged
        entry["by_category"] = group_outcomes(by_primitive, by="category", library=library)
        entry["by_provenance"] = group_outcomes(by_primitive, by="provenance", library=library)
    return entry
