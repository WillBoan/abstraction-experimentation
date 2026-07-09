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
from typing import TYPE_CHECKING

from arc_lab.core.annotation import Split
from arc_lab.core.dataset import Dataset
from arc_lab.core.task import Task
from arc_lab.eval.scoring import score_task
from arc_lab.solvers.dsl.analysis.artifact import (
    LEARNED_LIBRARY_FILE,
    RESULTS_FILE,
    RUNSPEC_FILE,
    TRACE_FILE,
    RunSpec,
    TaskRecord,
    append_record,
    as_float,
    as_int,
    git_commit,
    read_records,
)

if TYPE_CHECKING:
    from arc_lab.solvers.dsl.learn.sleep import SleepStrategy
from arc_lab.solvers.dsl.analysis.compression import CompressionMetric, SolvedTask
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
    """The committed, self-contained record of one run: spec + metrics + rows."""

    spec: RunSpec
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
    def solved_ids(self) -> frozenset[str]:
        """Task ids solved (test-level) in this run — the set for transfer diffs."""
        return frozenset(r.task_id for r in self.records if r.solved)

    @property
    def description_length(self) -> float:
        return self.library_bits + self.program_bits

    def summary_line(self) -> str:
        return (
            f"{self.spec.solver} on {self.spec.dataset}: "
            f"{self.solved}/{self.total} solved, "
            f"search_solved={self.search_solved}, considered={self.considered_total}, "
            f"DL={self.description_length:.1f} "
            f"(library={self.library_bits:.1f} + programs={self.program_bits:.1f})"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.spec.run_id(),
            "spec": self.spec.to_dict(),
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
        spec_raw = data["spec"]
        metrics_raw = data["metrics"]
        tasks_raw = data["tasks"]
        if not (
            isinstance(spec_raw, Mapping)
            and isinstance(metrics_raw, Mapping)
            and isinstance(tasks_raw, list)
        ):
            raise ValueError("malformed run summary")
        library = spec_raw["library"]
        config = spec_raw.get("config")
        commit = spec_raw.get("commit")
        spec = RunSpec(
            solver=str(spec_raw["solver"]),
            dataset=str(spec_raw["dataset"]),
            library=library if isinstance(library, Mapping) else {},
            config=config if isinstance(config, Mapping) else None,
            commit=commit if isinstance(commit, str) else None,
        )
        records = tuple(
            TaskRecord(
                task_id=str(row["task_id"]),
                solved=bool(row["solved"]),
                search_solved=bool(row["search_solved"]),
                considered=as_int(row["considered"]),
                program=(row["program"] if isinstance(row["program"], str) else None),
                program_size=(
                    row["program_size"] if isinstance(row["program_size"], int) else None
                ),
                program_dict=None,
                stats_extra={},
            )
            for row in tasks_raw
            if isinstance(row, Mapping)
        )
        return RunSummary(
            spec=spec,
            records=records,
            library_bits=as_float(metrics_raw["library_bits"]),
            program_bits=as_float(metrics_raw["program_bits"]),
        )


def execute(
    solver: ProgramSearchSolver,
    dataset: Dataset,
    *,
    sleep: SleepStrategy | None = None,
    out_dir: Path,
    metric: CompressionMetric | None = None,
    force: bool = False,
    progress: bool = False,
) -> tuple[RunSummary, Path]:
    """Execute ``solver`` over ``dataset``, writing a run artifact under ``out_dir``.

    The two execution activities share this core, parameterised by ``sleep``:

    * ``sleep is None`` — **Eval**: wake only, over the fixed ``solver.library``.
    * ``sleep`` given — **Synthesize**: first grow the library on the corpus's *train* split via
      :func:`~arc_lab.solvers.dsl.learn.loop.wake_sleep`, then eval the grown library; that library
      is written as ``learned_library.json`` (the run's *output*, distinct from the starting library
      the runspec records as its *input*).

    Returns the summary and the run directory. A completed run is served from cache (unless
    ``force``); a partial run is resumed. NOTE: the sleep strategy is not yet part of the run
    identity (Phase 14 folds the learn axes into ``Config``); until then, do not Eval and Synthesize
    the same solver+corpus into the same ``out_dir``.
    """
    metric = metric or CompressionMetric()
    spec = RunSpec(
        solver=solver.name,
        dataset=dataset.name,
        library=solver.library.to_dict(),
        config=None if solver.config is None else solver.config.to_dict(),
        commit=git_commit(),
    )
    run_dir = out_dir / spec.dir_name()
    results_path = run_dir / RESULTS_FILE
    trace_path = run_dir / TRACE_FILE

    if results_path.exists() and not force:
        cached = RunSummary.from_dict(json.loads(results_path.read_text(encoding="utf-8")))
        _warn_on_commit_mismatch(cached.spec.commit, spec.commit)
        return cached, run_dir

    run_dir.mkdir(parents=True, exist_ok=True)
    if force and trace_path.exists():
        trace_path.unlink()
    # The runspec (identity / inputs) is written first, so a crashed run still records what it was.
    (run_dir / RUNSPEC_FILE).write_text(
        json.dumps({"run_id": spec.run_id(), "spec": spec.to_dict()}, indent=2) + "\n",
        encoding="utf-8",
    )

    # Synthesize: grow the library on the corpus's train split before evaluating (deterministic,
    # so a resumed run rebuilds the same library). Eval (sleep=None) leaves the library untouched.
    if sleep is not None:
        from arc_lab.solvers.dsl.learn.loop import wake_sleep

        train = [
            e.task for e in dataset.entries if e.meta is not None and e.meta.split is Split.TRAIN
        ]
        grown = wake_sleep(
            library=solver.library, search=solver.search, tasks=train, sleep=sleep, cost=solver.cost
        ).library
        solver = ProgramSearchSolver(
            library=grown,
            search=solver.search,
            cost=solver.cost,
            name=solver.name,
            config=solver.config,
        )

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
        spec=spec,
        records=tuple(records),
        library_bits=dl.library_bits,
        program_bits=dl.program_bits,
    )
    results_path.write_text(json.dumps(summary.to_dict(), indent=2) + "\n", encoding="utf-8")
    if sleep is not None:  # the grown library is the run's output
        (run_dir / LEARNED_LIBRARY_FILE).write_text(
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


def _corpus(records: list[TaskRecord], dataset: Dataset) -> list[SolvedTask]:
    """The solved corpus: (annotated task, program) for every record that found a program."""
    entries: list[SolvedTask] = []
    for record in records:
        if record.program_dict is None:
            continue
        entries.append(
            SolvedTask(
                dataset.get_annotated(record.task_id), Program.from_dict(record.program_dict)
            )
        )
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


def iter_run_summaries(runs_dir: Path) -> list[RunSummary]:
    """Load every run summary under ``runs_dir`` (``<run>/summary.json``), for listing."""
    if not runs_dir.is_dir():
        return []
    return [
        RunSummary.from_dict(json.loads(path.read_text(encoding="utf-8")))
        for path in sorted(runs_dir.glob("*/results.json"))
    ]
