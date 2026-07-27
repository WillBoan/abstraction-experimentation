"""Recorded probe costs, read back by ladder — measured numbers WITHOUT a second source of truth.

A `.ladder` file must not carry measured costs ([LADDER-FORMAT.md] keeps chosen and derived
separate, and a stale cost comment is worse than none). But the numbers still want to sit next to
the rung table, because that is where the design decision gets made.

Since probe cells became recorded runs (2026-07-26) they can simply be READ. Each cell's corpus is
named ``probe:<ladder>:<library>:<task>``, so the ladder's own cells are a prefix scan over
``runs/`` — no index, no cache file, nothing to keep in sync. What was measured is wherever it was
written down, and if it was never measured there is nothing to show.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from arc_lab.program_search.execution.execute import DEFAULT_RUNS_ROOT
from arc_lab.program_search.execution.model.run_record import (
    RUNSPEC_FILENAME,
    RunRecord,
    iter_run_dirs,
)
from arc_lab.program_search.ladders.probe import PROBE_CORPUS_PREFIX


@dataclass(frozen=True, slots=True)
class RecordedCell:
    """One recorded probe cell: what it cost, and whether the number is a measurement."""

    library: str
    task_id: str
    considered: int
    censored: bool

    @property
    def display(self) -> str:
        """``censored`` means the guard stopped it, so the count is a floor, not a cost."""
        return f">{self.considered:,}" if self.censored else f"{self.considered:,}"


def recorded_probe_cells(
    ladder: str, *, runs_root: Path | None = None
) -> dict[tuple[str, str], RecordedCell]:
    """Every recorded probe cell for ``ladder``, keyed ``(library name, task id)``.

    Empty when nothing has been probed -- which is the honest answer, not a gap to fill in with an
    estimate. Pruned cells are included: their library name ends ``:pruned`` and they are the
    floor-tax denominator.
    """
    root = DEFAULT_RUNS_ROOT if runs_root is None else runs_root
    if not root.is_dir():
        return {}
    wanted = f"{PROBE_CORPUS_PREFIX}{ladder}:"
    out: dict[tuple[str, str], RecordedCell] = {}
    for run_dir in iter_run_dirs(root):
        spec_path = run_dir / RUNSPEC_FILENAME
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue  # a torn or half-written run dir is not a measurement
        name = str(spec.get("corpus_name", ""))
        if not name.startswith(wanted):
            continue
        record = RunRecord(run_id=str(spec.get("run_id", "")), run_dir=run_dir)
        if not record.completed:
            continue
        library, _, task_id = name[len(wanted) :].rpartition(":")
        cell = _cell_from(record, library, task_id)
        if cell is not None:
            out[(library, task_id)] = cell
    return out


def _cell_from(record: RunRecord, library: str, task_id: str) -> RecordedCell | None:
    for row in record.trace_rows():
        if row.get("task_id") != task_id:
            continue
        stats = row.get("search_stats")
        if not isinstance(stats, Mapping):
            return None
        total = stats.get("total")
        considered = total.get("considered") if isinstance(total, Mapping) else None
        if not isinstance(considered, int):
            return None
        return RecordedCell(
            library=library,
            task_id=task_id,
            considered=considered,
            censored=bool(stats.get("censored")),
        )
    return None
