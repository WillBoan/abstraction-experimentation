"""``RunRecord``: the read-side handle to a recorded run's artifacts.

What ``execute()`` returns and what ``analyze_run`` / ``create_study_report``
consume — keeping *spec* (input identity, ``RunSpec``) and *record* (output
artifacts) as two distinct types. Artifact filenames are defined here, once, so
the writer (``execute``) and every reader agree.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from .results import TaskResult

if TYPE_CHECKING:
    from arc_lab.program_search.substrate.library import Library

#: Written FIRST — a run's identity survives a crash.
RUNSPEC_FILENAME: Final = "runspec.json"
#: Written LAST — its presence marks the run complete (the idempotency check).
RESULTS_FILENAME: Final = "results.json"
#: Streamed per task — the resumable checkpoint; a gitignored, regenerable cache.
TRACE_FILENAME: Final = "trace.jsonl"
#: LEARN runs only: the grown library.
LEARNED_LIBRARY_FILENAME: Final = "learned_library.json"
#: Reservoir samples from the run's ``TraceSpec`` — only covers tasks executed in the
#: ``execute()`` call that wrote it (a resume's already-traced tasks aren't re-sampled).
SAMPLES_FILENAME: Final = "samples.json"
#: Full per-candidate capture (``TraceSpec.capture_all``), one JSONL file per task/wake.
CAPTURE_DIRNAME: Final = "capture"
#: Capture settings + counts (loud truncation) for whichever tasks used full capture.
MANIFEST_FILENAME: Final = "manifest.json"


def find_run_dir(root: Path, run_id: str) -> Path | None:
    """Locate an existing ``runs/<started_at>_<run_id>/`` dir by its content-hash suffix.

    ``run_id`` stays the content-addressed identity (the cache key); the on-disk
    dirname is prefixed with a start timestamp purely so ``runs/`` sorts and reads
    chronologically. The two are decoupled — never join ``root / run_id`` directly.
    """
    matches = sorted(root.glob(f"*_{run_id}")) if root.is_dir() else []
    if len(matches) > 1:
        raise RuntimeError(f"multiple run dirs match run_id {run_id!r} under {root}: {matches}")
    return matches[0] if matches else None


@dataclass(frozen=True, slots=True)
class RunRecord:
    """A completed (or in-progress) run's artifacts, loaded lazily."""

    run_id: str
    run_dir: Path

    @property
    def runspec_path(self) -> Path:
        return self.run_dir / RUNSPEC_FILENAME

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
    def manifest_path(self) -> Path:
        return self.run_dir / MANIFEST_FILENAME

    @property
    def completed(self) -> bool:
        """True iff ``results.json`` exists — the cache-hit test ``execute`` runs first."""
        return self.results_path.is_file()

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

    def samples(self) -> dict[str, object] | None:
        """The ``TraceSpec`` reservoir samples, or ``None`` if the run predates tracing / used
        no samplers — unlike ``results()``, absence is not an error (an optional artifact)."""
        if not self.samples_path.is_file():
            return None
        with self.samples_path.open(encoding="utf-8") as handle:
            data: object = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"malformed {SAMPLES_FILENAME} in {self.run_dir}")
        return data

    def manifest(self) -> dict[str, object] | None:
        """The capture manifest (settings + counts + loud truncation flags), or ``None`` if
        ``TraceSpec.capture_all`` was never used for this run."""
        if not self.manifest_path.is_file():
            return None
        with self.manifest_path.open(encoding="utf-8") as handle:
            data: object = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"malformed {MANIFEST_FILENAME} in {self.run_dir}")
        return data

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
