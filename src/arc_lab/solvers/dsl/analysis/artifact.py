"""The durable per-run artifact: coordinates, per-task records, and derived metrics.

A *run* is the atomic unit of experimentation — one solver over one dataset with one
library. It is fully pinned by its **coordinates** in the (floor x curriculum x
machinery) design space, and because solvers are deterministic (no RNG), the run is a
pure function of those coordinates. Two consequences we lean on:

* the ``run_id`` is a **content hash of the coordinates**, so re-running is idempotent
  and comparable (same experiment → same id);
* the raw ``trace.jsonl`` is a regenerable **cache**, so it is gitignored while the
  small ``summary.json`` (+ ``library.json``) are the committed, self-contained record.

We store **observations** (programs, sizes, counts), not derived ratios — a metric
redefinition then recomputes offline from two runs' recorded description lengths rather
than forcing a re-run. Commit SHA is recorded (not hashed into the id: an unrelated
commit shouldn't invalidate the cache) so a stale cached run can be flagged on load.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arc_lab.solvers.dsl.config import Config

TRACE_FILE = "trace.jsonl"
RUNSPEC_FILE = "runspec.json"
RESULTS_FILE = "results.json"
LEARNED_LIBRARY_FILE = "learned_library.json"


def _slug(text: str) -> str:
    """Filesystem-safe rendering of a name (alphanumerics, hyphen, underscore kept)."""
    return "".join(c if (c.isalnum() or c in "-_") else "-" for c in text)


def git_commit() -> str | None:
    """Best-effort short commit SHA of the working tree, or ``None`` outside a repo."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


@dataclass(frozen=True, slots=True)
class RunSpec:
    """The identity that pins a run: solver + corpus + machinery (config) + commit.

    ``run_id`` is a content hash of everything but the commit, so re-running is idempotent —
    and, crucially, two runs differing only in a search *parameter* (carried in ``config``) get
    distinct ids. The pre-config, name-only coordinates could not see that difference, so such
    runs would collide on one directory and cache-clobber each other. ``config`` is ``None`` for a
    solver built directly over a learned library (a study's L2/L3), which differ by ``library``.
    """

    solver: str
    dataset: str
    library: Mapping[str, object]  # Library.to_dict(): the vocabulary (floor) identity
    config: Config | None = None  # the machinery (search params + cost); None for a raw solver
    commit: str | None = None

    def run_id(self) -> str:
        """Deterministic content hash of the spec (commit deliberately excluded)."""
        payload = json.dumps(
            {
                "solver": self.solver,
                "dataset": self.dataset,
                "library": self.library,
                "config": None if self.config is None else self.config.to_dict(),
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def dir_name(self) -> str:
        """A legible, still-unique run directory: ``<solver>_<dataset>_<hash>``.

        Solver + dataset are part of the hashed spec, so prefixing with them stays deterministic
        (same spec → same directory → the cache still hits) while making ``runs/`` navigable by
        eye instead of an opaque hash.
        """
        return f"{_slug(self.solver)}_{_slug(self.dataset)}_{self.run_id()}"

    def to_dict(self) -> dict[str, object]:
        return {
            "solver": self.solver,
            "dataset": self.dataset,
            "library": dict(self.library),
            "config": None if self.config is None else self.config.to_dict(),
            "commit": self.commit,
        }


@dataclass(frozen=True, slots=True)
class TaskRecord:
    """One task's outcome, rich enough to feed metrics and (via ``program``) the loop."""

    task_id: str
    solved: bool  # test-level: the scorer's exact-match verdict
    search_solved: bool  # train-level: a program consistent with training was found
    considered: int  # search effort (nodes examined) — the speedup signal
    program: str | None  # human-readable str(program)
    program_size: int | None
    program_dict: Mapping[str, object] | None  # machine round-trip (Program.from_dict)
    stats_extra: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "solved": self.solved,
            "search_solved": self.search_solved,
            "considered": self.considered,
            "program": self.program,
            "program_size": self.program_size,
            "program_dict": None if self.program_dict is None else dict(self.program_dict),
            "stats_extra": dict(self.stats_extra),
        }

    @staticmethod
    def from_dict(data: Mapping[str, object]) -> TaskRecord:
        task_id = data["task_id"]
        program = data["program"]
        program_dict = data["program_dict"]
        stats_extra = data["stats_extra"]
        if not isinstance(task_id, str):
            raise ValueError(f"malformed task record: {data!r}")
        return TaskRecord(
            task_id=task_id,
            solved=bool(data["solved"]),
            search_solved=bool(data["search_solved"]),
            considered=as_int(data["considered"]),
            program=program if isinstance(program, str) else None,
            program_size=_opt_int(data["program_size"]),
            program_dict=program_dict if isinstance(program_dict, Mapping) else None,
            stats_extra=_int_map(stats_extra),
        )


def as_int(value: object) -> int:
    """Narrow a JSON-decoded value to ``int`` (rejecting ``bool``), for typed parsing."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"expected an int, got {value!r}")
    return value


def as_float(value: object) -> float:
    """Narrow a JSON-decoded number (``int`` or ``float``, not ``bool``) to ``float``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"expected a number, got {value!r}")
    return float(value)


def _opt_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _int_map(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(k): int(v) for k, v in value.items() if isinstance(v, int)}


def append_record(trace_path: Path, record: TaskRecord) -> None:
    """Stream one record to the trace as a JSON line (flushed for crash-safety)."""
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record.to_dict()) + "\n")
        handle.flush()


def read_records(trace_path: Path) -> list[TaskRecord]:
    """Read previously-written records from a (possibly partial) trace, for resume."""
    if not trace_path.exists():
        return []
    records: list[TaskRecord] = []
    for raw_line in trace_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parsed = json.loads(line)
        if isinstance(parsed, Mapping):
            records.append(TaskRecord.from_dict(parsed))
    return records
