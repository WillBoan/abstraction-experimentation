"""Drive a program-search solver over a dataset and emit a run artifact.

This is the DSL-introspective sibling of ``eval.runner``: where that one is
solver-agnostic and reports solve-count only, this one reaches into a
:class:`ProgramSearchSolver` to capture the *program it found* and the *search stats*
per task, then computes the run's description length. It deliberately does **not** flow
through the narrow ``Solver.predict`` contract — it calls ``search.find`` directly and
ranks with the solver's own ``cost``, mirroring ``predict`` without widening it.

Idempotent + resumable, both falling out of determinism: a completed run (``summary.json``
present) is returned from cache unless ``force``; a crash mid-run leaves a partial
``trace.jsonl`` that is picked up and continued.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from arc_lab.core.dataset import Dataset
from arc_lab.core.task import Task
from arc_lab.eval.scoring import score_task
from arc_lab.solvers.dsl.analysis.artifact import (
    LIBRARY_FILE,
    SUMMARY_FILE,
    TRACE_FILE,
    RunCoordinates,
    TaskRecord,
    append_record,
    as_float,
    as_int,
    git_commit,
    read_records,
)
from arc_lab.solvers.dsl.analysis.compression import CompressionMetric, CorpusEntry
from arc_lab.solvers.dsl.solver import ProgramSearchSolver
from arc_lab.solvers.dsl.substrate.program import Input, Program
from arc_lab.solvers.dsl.trace import task_context

logger = logging.getLogger(__name__)

# TODO(experiment-db, discussion-point): cross-run analysis (charting the
# floor x machinery tradeoff surface) is served today by querying the committed
# summary.json files directly — e.g. duckdb.sql("... FROM 'runs/*/summary.json'") or
# pandas — with zero infra. A real DB + admin UI only earns its place at
# thousands-of-runs / concurrent writers / a shared live dashboard, and even then the
# first step is DuckDB/parquet *over these files* (additive, files stay source of truth),
# not a bespoke store. Deferred deliberately; see the design discussion, not a schema.

#: When search finds nothing, fall back to identity so scoring never crashes.
_FALLBACK: Program = Input()


@dataclass(frozen=True, slots=True)
class RunSummary:
    """The committed, self-contained record of one run: coordinates + metrics + rows."""

    coordinates: RunCoordinates
    records: tuple[TaskRecord, ...]
    library_bits: float
    program_bits: float

    @property
    def total(self) -> int:
        return len(self.records)

    @property
    def solved(self) -> int:
        return sum(r.solved for r in self.records)

    @property
    def search_solved(self) -> int:
        return sum(r.search_solved for r in self.records)

    @property
    def considered_total(self) -> int:
        return sum(r.considered for r in self.records)

    @property
    def description_length(self) -> float:
        return self.library_bits + self.program_bits

    def summary_line(self) -> str:
        return (
            f"{self.coordinates.solver} on {self.coordinates.dataset}: "
            f"{self.solved}/{self.total} solved, "
            f"search_solved={self.search_solved}, considered={self.considered_total}, "
            f"DL={self.description_length:.1f} "
            f"(library={self.library_bits:.1f} + programs={self.program_bits:.1f})"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.coordinates.run_id(),
            "coordinates": self.coordinates.to_dict(),
            "metrics": {
                "solved": self.solved,
                "total": self.total,
                "search_solved": self.search_solved,
                "considered_total": self.considered_total,
                "library_bits": self.library_bits,
                "program_bits": self.program_bits,
                "description_length": self.description_length,
            },
            # Light per-task rows (no program_dict — that lives in the regenerable trace).
            "tasks": [
                {
                    "task_id": r.task_id,
                    "solved": r.solved,
                    "search_solved": r.search_solved,
                    "considered": r.considered,
                    "program": r.program,
                    "program_size": r.program_size,
                }
                for r in self.records
            ],
        }

    @staticmethod
    def from_dict(data: Mapping[str, object]) -> RunSummary:
        coords_raw = data["coordinates"]
        metrics_raw = data["metrics"]
        tasks_raw = data["tasks"]
        if not (
            isinstance(coords_raw, Mapping)
            and isinstance(metrics_raw, Mapping)
            and isinstance(tasks_raw, list)
        ):
            raise ValueError("malformed run summary")
        library = coords_raw["library"]
        commit = coords_raw["commit"]
        coordinates = RunCoordinates(
            solver=str(coords_raw["solver"]),
            dataset=str(coords_raw["dataset"]),
            library=library if isinstance(library, Mapping) else {},
            commit=commit if isinstance(commit, str) else None,
        )
        records = tuple(
            TaskRecord(
                task_id=str(row["task_id"]),
                solved=bool(row["solved"]),
                search_solved=bool(row["search_solved"]),
                considered=as_int(row["considered"]),
                program=(row["program"] if isinstance(row["program"], str) else None),
                program_size=(row["program_size"] if isinstance(row["program_size"], int) else None),
                program_dict=None,
                stats_extra={},
            )
            for row in tasks_raw
            if isinstance(row, Mapping)
        )
        return RunSummary(
            coordinates=coordinates,
            records=records,
            library_bits=as_float(metrics_raw["library_bits"]),
            program_bits=as_float(metrics_raw["program_bits"]),
        )


def analyze(
    solver: ProgramSearchSolver,
    dataset: Dataset,
    *,
    out_dir: Path,
    metric: CompressionMetric | None = None,
    force: bool = False,
    progress: bool = False,
) -> tuple[RunSummary, Path]:
    """Run ``solver`` over ``dataset``, writing a run artifact under ``out_dir``.

    Returns the summary and the run directory. A completed run is served from cache
    (unless ``force``); a partial run is resumed.
    """
    metric = metric or CompressionMetric()
    coordinates = RunCoordinates(
        solver=solver.name,
        dataset=dataset.name,
        library=solver.library.to_dict(),
        commit=git_commit(),
    )
    run_dir = out_dir / coordinates.run_id()
    summary_path = run_dir / SUMMARY_FILE
    trace_path = run_dir / TRACE_FILE

    if summary_path.exists() and not force:
        cached = RunSummary.from_dict(json.loads(summary_path.read_text(encoding="utf-8")))
        _warn_on_commit_mismatch(cached.coordinates.commit, coordinates.commit)
        return cached, run_dir

    run_dir.mkdir(parents=True, exist_ok=True)
    if force and trace_path.exists():
        trace_path.unlink()
    existing = read_records(trace_path)
    done = {r.task_id for r in existing}
    records: list[TaskRecord] = list(existing)

    for i, task in enumerate(dataset, start=1):
        if task.task_id not in done:
            record = _run_task(solver, task)
            append_record(trace_path, record)
            records.append(record)
        if progress:
            _emit_progress(records[-1], i, len(dataset))
    if progress:
        print(flush=True)

    dl = metric.describe(_corpus(records, dataset), solver.library)
    summary = RunSummary(
        coordinates=coordinates,
        records=tuple(records),
        library_bits=dl.library_bits,
        program_bits=dl.program_bits,
    )
    summary_path.write_text(json.dumps(summary.to_dict(), indent=2) + "\n", encoding="utf-8")
    (run_dir / LIBRARY_FILE).write_text(
        json.dumps(solver.library.to_dict(), indent=2) + "\n", encoding="utf-8"
    )
    return summary, run_dir


def _run_task(solver: ProgramSearchSolver, task: Task) -> TaskRecord:
    with task_context(task.task_id):
        result = solver.search.find(task, solver.library)
    programs = list(result.programs)
    chosen = (
        min(programs, key=lambda p: solver.cost.of(p, task, solver.library)) if programs else None
    )
    return TaskRecord(
        task_id=task.task_id,
        solved=_score(solver, task, programs),
        search_solved=result.stats.solved,
        considered=result.stats.considered,
        program=str(chosen) if chosen is not None else None,
        program_size=chosen.size() if chosen is not None else None,
        program_dict=chosen.to_dict() if chosen is not None else None,
        stats_extra=dict(result.stats.extra),
    )


def _score(solver: ProgramSearchSolver, task: Task, programs: list[Program]) -> bool:
    """Best-effort test-set verdict, mirroring ``predict`` but never raising.

    A missing ground truth (hidden test set) or a program that errors on a test input
    yields ``False`` rather than aborting the run.
    """
    ranked = sorted(programs or [_FALLBACK], key=lambda p: solver.cost.of(p, task, solver.library))
    try:
        prediction = [
            [program.evaluate_grid(example.input, solver.library) for program in ranked]
            for example in task.test
        ]
        solved, _ = score_task(task, prediction)
    except Exception:
        # Scoring is best-effort: a hidden test set (no ground truth) or a program
        # that errors on a test input counts as unsolved, never aborts the run.
        return False
    return solved


def _corpus(records: list[TaskRecord], dataset: Dataset) -> list[CorpusEntry]:
    """The solved corpus: (task, program) for every record that found a program."""
    entries: list[CorpusEntry] = []
    for record in records:
        if record.program_dict is None:
            continue
        entries.append((dataset.get(record.task_id), Program.from_dict(record.program_dict)))
    return entries


def _warn_on_commit_mismatch(cached: str | None, current: str | None) -> None:
    if cached is not None and current is not None and cached != current:
        logger.warning(
            "cached run was recorded at commit %s but HEAD is %s; pass force to re-run",
            cached,
            current,
        )


def _emit_progress(record: TaskRecord, index: int, total: int) -> None:
    mark = "O" if record.solved else ("+" if record.search_solved else ".")
    print(mark, end="", flush=True)
    if index % 50 == 0:
        print(f"  {index}/{total}", flush=True)
