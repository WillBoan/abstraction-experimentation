"""``RunRecord``: the read-side handle to a recorded run's artifacts.

What ``execute()`` returns and what ``analyze_run`` / ``create_study_report``
consume — keeping *spec* (input identity, ``RunSpec``) and *record* (output
artifacts) as two distinct types. Artifact filenames are defined here, once, so
the writer (``execute``) and every reader agree.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from .results import TaskResult


def considered_total(results: Mapping[str, object]) -> int | None:
    """The run-wide ``considered`` count from a ``results.json`` payload — reads the current
    ``search_stats.total.considered`` location, so callers don't hand-navigate the nested block."""
    search_stats = results.get("search_stats")
    if isinstance(search_stats, dict):
        total = search_stats.get("total")
        if isinstance(total, dict) and isinstance(total.get("considered"), int):
            return int(total["considered"])
    return None


if TYPE_CHECKING:
    from arc_lab.program_search.substrate.library import Library

#: Written FIRST — a run's identity survives a crash.
RUNSPEC_FILENAME: Final = "runspec.json"
#: Real-time execution log — written throughout the run (``execute.py``'s ``_run_log_handler``),
#: always on regardless of the CLI's ``-v``/``-vv`` flags (those only govern console output).
LOG_FILENAME: Final = "run.log"
#: Written LAST — its presence marks the run complete (the idempotency check).
RESULTS_FILENAME: Final = "results.json"
#: Streamed per task — the resumable checkpoint; a gitignored, regenerable cache.
TRACE_FILENAME: Final = "trace.jsonl"
#: LEARN runs only: the grown library.
LEARNED_LIBRARY_FILENAME: Final = "learned_library.json"
#: Reservoir samples from the run's ``TraceSpec`` — JSONL, one row per (task, primitive, outcome,
#: sampled program). Only covers tasks executed in the ``execute()`` call that wrote it (a
#: resume's already-traced tasks aren't re-sampled).
SAMPLES_FILENAME: Final = "samples.jsonl"
#: Full per-candidate capture (``TraceSpec.capture_all``), one JSONL file per task/wake.
CAPTURE_DIRNAME: Final = "capture"
#: Capture settings + counts (loud truncation) — lives inside ``capture/``; the ``_`` sorts it
#: first and marks it as metadata about the per-task streams beside it.
CAPTURE_SUMMARY_FILENAME: Final = "_capture_summary.json"
#: cProfile artifacts (``TraceSpec.profile``): raw stats + a rendered summary, in their own subdir.
PROFILE_DIRNAME: Final = "profile"
PROFILE_STATS_FILENAME: Final = "stats.prof"
PROFILE_SUMMARY_FILENAME: Final = "summary.txt"


def find_run_dir(root: Path, run_id: str) -> Path | None:
    """Locate an existing ``runs/<date>/<started_at>_<run_id>/`` dir by its content-hash suffix.

    ``run_id`` stays the content-addressed identity (the cache key); the on-disk dirname is
    prefixed with a start timestamp purely so ``runs/`` sorts chronologically, and grouped under a
    ``<date>`` subfolder for navigability. The two are decoupled — never join ``root / run_id``.
    Both the current date-grouped layout (``root/<date>/<dir>``) and the legacy flat one
    (``root/<dir>``) are searched, so runs recorded before grouping still resolve as cache hits.
    """
    if not root.is_dir():
        return None
    matches = sorted(root.glob(f"*_{run_id}")) + sorted(root.glob(f"*/*_{run_id}"))
    if len(matches) > 1:
        raise RuntimeError(f"multiple run dirs match run_id {run_id!r} under {root}: {matches}")
    return matches[0] if matches else None


def iter_run_dirs(root: Path) -> list[Path]:
    """Every run directory under ``root``, sorted — a run dir is one that holds a ``runspec.json``,
    found in both the date-grouped (``root/<date>/<dir>``) and legacy flat (``root/<dir>``)
    layouts. The two globs are disjoint (a date folder holds no ``runspec.json``; a run dir's
    ``capture/`` subdir holds none either), so there is no double-counting."""
    if not root.is_dir():
        return []
    specs = sorted(root.glob(f"*/{RUNSPEC_FILENAME}")) + sorted(
        root.glob(f"*/*/{RUNSPEC_FILENAME}")
    )
    return [spec.parent for spec in specs]


@dataclass(frozen=True, slots=True)
class RunRecord:
    """A completed (or in-progress) run's artifacts, loaded lazily."""

    run_id: str
    run_dir: Path

    @property
    def runspec_path(self) -> Path:
        return self.run_dir / RUNSPEC_FILENAME

    @property
    def log_path(self) -> Path:
        return self.run_dir / LOG_FILENAME

    @property
    def results_path(self) -> Path:
        return self.run_dir / RESULTS_FILENAME

    @property
    def trace_path(self) -> Path:
        return self.run_dir / TRACE_FILENAME

    @property
    def learned_library_path(self) -> Path:
        return self.run_dir / LEARNED_LIBRARY_FILENAME

    @property
    def samples_path(self) -> Path:
        return self.run_dir / SAMPLES_FILENAME

    @property
    def capture_dir(self) -> Path:
        return self.run_dir / CAPTURE_DIRNAME

    @property
    def capture_summary_path(self) -> Path:
        return self.capture_dir / CAPTURE_SUMMARY_FILENAME

    @property
    def profile_dir(self) -> Path:
        return self.run_dir / PROFILE_DIRNAME

    @property
    def profile_stats_path(self) -> Path:
        return self.profile_dir / PROFILE_STATS_FILENAME

    @property
    def profile_summary_path(self) -> Path:
        return self.profile_dir / PROFILE_SUMMARY_FILENAME

    @property
    def completed(self) -> bool:
        """True iff ``results.json`` exists — the cache-hit test ``execute`` runs first."""
        return self.results_path.is_file()

    def runspec(self) -> dict[str, object]:
        """The run's identity + provenance payload (``config``, ``corpus_name``, ``commit``), parsed.

        Written first by ``execute``, so it is present even for a crashed run -- unlike
        :meth:`results`, whose absence is what ``completed`` tests for."""
        with self.runspec_path.open(encoding="utf-8") as handle:
            data: object = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"malformed {RUNSPEC_FILENAME} in {self.run_dir}")
        return data

    def results(self) -> dict[str, object]:
        """The run-level results payload (metrics + per-task rows), parsed."""
        with self.results_path.open(encoding="utf-8") as handle:
            data: object = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"malformed {RESULTS_FILENAME} in {self.run_dir}")
        return data

    def task_results(self) -> tuple[TaskResult, ...]:
        """The per-task rows of ``results.json`` as records."""
        rows = self.results().get("tasks")
        if not isinstance(rows, list):
            raise ValueError(f"{RESULTS_FILENAME} in {self.run_dir} has no 'tasks' rows")
        return tuple(TaskResult.from_dict(row) for row in rows)

    def sample_rows(self) -> list[dict[str, object]] | None:
        """The ``TraceSpec`` reservoir samples as flat rows (``task``, ``candidate_index``,
        ``primitive``, ``outcome``, ``program``), or ``None`` if the run predates tracing / used
        no samplers — unlike ``results()``, absence is not an error (an optional artifact)."""
        if not self.samples_path.is_file():
            return None
        rows: list[dict[str, object]] = []
        with self.samples_path.open(encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                row: object = json.loads(line)
                if isinstance(row, dict):
                    rows.append(row)
        return rows

    def capture_summary(self) -> dict[str, object] | None:
        """The capture summary (settings + counts + loud truncation flags), or ``None`` if
        ``TraceSpec.capture_all`` was never used for this run."""
        if not self.capture_summary_path.is_file():
            return None
        with self.capture_summary_path.open(encoding="utf-8") as handle:
            data: object = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"malformed {CAPTURE_SUMMARY_FILENAME} in {self.run_dir}")
        return data

    def profile_summary(self) -> str | None:
        """The rendered cProfile summary text (``TraceSpec.profile``), or ``None`` if the run was
        never profiled - an optional diagnostic artifact, so absence is not an error."""
        if not self.profile_summary_path.is_file():
            return None
        return self.profile_summary_path.read_text(encoding="utf-8")

    def trace_rows(self) -> Iterator[dict[str, object]]:
        """Stream the trace rows (skipping a trailing partial line after a crash)."""
        if not self.trace_path.is_file():
            return
        with self.trace_path.open(encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    row: object = json.loads(line)
                except json.JSONDecodeError:
                    return  # a torn final write — everything before it is intact
                if isinstance(row, dict):
                    yield row

    def learned_library(self) -> Library:
        """Load the grown library (LEARN runs only)."""
        from arc_lab.program_search.substrate.library import Library

        with self.learned_library_path.open(encoding="utf-8") as handle:
            data: object = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"malformed {LEARNED_LIBRARY_FILENAME} in {self.run_dir}")
        return Library.from_dict(data)

    def config_library(self) -> Library:
        """The run's own ``Config.library`` (any run kind), read straight from ``runspec.json`` —
        no registry needed, mirroring ``learned_library``'s direct ``Library.from_dict``."""
        from arc_lab.program_search.substrate.library import Library

        with self.runspec_path.open(encoding="utf-8") as handle:
            data: object = json.load(handle)
        config = data.get("config") if isinstance(data, dict) else None
        library_data = config.get("library") if isinstance(config, dict) else None
        if not isinstance(library_data, dict):
            raise ValueError(f"malformed {RUNSPEC_FILENAME} in {self.run_dir}: no config.library")
        return Library.from_dict(library_data)
