"""``execute``: the recorded-run core — the ONLY writer of ``runs/`` (EXECUTION.md).

One ``execute(run_spec)`` = one recorded run, addressed by ``run_id``:

- **Idempotent** — a present ``results.json`` is served from cache, no execution.
- **Crash-safe** — ``runspec.json`` is written *first* (identity survives a crash);
  ``results.json`` is written *last* (its presence marks completion).
- **Resumable** — per-task rows stream to ``trace.jsonl`` as they finish; on restart,
  already-traced tasks are served from the trace and only the remainder runs.
- **Isolated** — one broken task never aborts the run: its row records the error and
  an all-False score.

``config.learn is None`` ⇒ the SEARCH branch. ``config.learn`` set ⇒ the LEARN
branch: the wake-sleep loop, ONE recorded run whose artifact is the grown library
(``learned_library.json``) — its trace checkpoints at iteration grain (each sleep row
carries the library), and the loop ends with sleep (the final wake is the derived
SEARCH run the activity executes; see ``run_search_learn``).

``trace: TraceSpec`` governs what gets *observed* about the search (outcome sampling / full
capture) — never part of ``run_id`` (``model/trace_spec.py``'s docstring has the determinism
argument for why that's sound). ``force_recapture=True`` re-executes an already-completed run
purely to (re)populate its telemetry artifacts under a new ``TraceSpec``.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, TextIO

from arc_lab.core.task import Task
from arc_lab.eval.scoring import score_task
from arc_lab.program_search.analysis.compression import SolvedTask
from arc_lab.program_search.search.search_result import SearchResult, SearchStats
from arc_lab.program_search.search.tracking import (
    OUTCOME_NAMES,
    Outcome,
    SearchTracker,
    funnel_outcomes,
)
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Program

from .model.config import Config
from .model.results import TaskResult, TaskScore
from .model.run_record import RunRecord, find_run_dir
from .model.run_spec import RunSpec
from .model.trace_spec import TraceSpec
from .predict import predict

logger = logging.getLogger(__name__)

#: Repo-root ``runs/`` — the gitignored, regenerable artifact cache.
DEFAULT_RUNS_ROOT: Final = Path(__file__).resolve().parents[4] / "runs"


def execute(
    run_spec: RunSpec,
    *,
    runs_root: Path | None = None,
    trace: TraceSpec | None = None,
    force_recapture: bool = False,
) -> RunRecord:
    """Execute (or serve from cache) the recorded run ``run_spec`` names.

    ``trace`` defaults to ``TraceSpec()`` (small deterministic sampling, no full capture) rather
    than "no tracing at all" — the default-on sampling tier is cheap enough to always be worth it.
    ``force_recapture`` bypasses the idempotency cache for an already-completed run and clears its
    ``trace.jsonl``/``results.json`` so it re-executes from scratch (sound because deterministic:
    the re-run reproduces identical results, differing only in wall-clock ``seconds`` and whatever
    the new ``TraceSpec`` observes).
    """
    root = DEFAULT_RUNS_ROOT if runs_root is None else runs_root
    run_dir = find_run_dir(root, run_spec.run_id)
    if run_dir is None:
        run_dir = root / f"{_timestamp()}_{run_spec.run_id}"
    record = RunRecord(run_id=run_spec.run_id, run_dir=run_dir)
    trace_spec = trace if trace is not None else TraceSpec()

    if record.completed and not force_recapture:  # idempotency: results.json present ⇒ cached
        logger.info("run %s served from cache (%s)", record.run_id, record.run_dir)
        return record
    if force_recapture and record.completed:
        logger.info("run %s: force-recapture, re-executing for a fresh TraceSpec", record.run_id)
        record.trace_path.unlink(missing_ok=True)
        record.results_path.unlink()  # absence un-marks completion; execute() below regenerates it

    record.run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        record.runspec_path,
        {**run_spec.to_dict(), "commit": _current_commit(), "run_started_at": _now_iso()},
    )

    if run_spec.config.learn is None:
        payload = _search_results(_run_search(run_spec, record, trace_spec))
    else:
        payload = _run_learn(run_spec, record, trace_spec)

    _write_json(
        record.results_path,  # the LAST write — its presence marks the run complete
        {"run_id": record.run_id, "corpus_name": run_spec.corpus.name, **payload},
    )
    logger.info("run %s recorded to %s", record.run_id, record.run_dir)
    return record


# -- tracing: sampling + full capture, wired into every search call -------------


@dataclass(slots=True)
class _CaptureSink:
    """Streams every observed candidate to one JSONL file, capped — the file I/O
    ``SearchTracker`` itself never does (``search/tracking.py``); this is the plain callable it's
    handed. Opens its file lazily (only once a candidate actually arrives), so a task that
    considers nothing never creates an empty capture file. Rows are written in *outcome-resolution*
    order (not generation order); each carries its ``candidate_index`` so a reader can sort back.
    """

    path: Path
    max_count: int
    captured: int = 0
    truncated: bool = False
    _handle: TextIO | None = field(default=None, repr=False)

    def __call__(
        self, candidate_index: int, program: Program, primitives: frozenset[str], outcome: Outcome
    ) -> None:
        if self.captured >= self.max_count:
            self.truncated = True
            return
        if self._handle is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = self.path.open("w", encoding="utf-8")
        row = {
            "candidate_index": candidate_index,
            "outcome": outcome.value,
            "primitives": sorted(primitives),
            "program": str(program),
        }
        self._handle.write(json.dumps(row) + "\n")
        self.captured += 1

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()


@dataclass(frozen=True, slots=True)
class _TrackedOutcome:
    """What one tracked search call yields beyond its ``SearchResult`` — the pieces
    ``execute()`` needs for ``samples.jsonl``/``_capture_summary.json``, not the trace row itself."""

    sample_rows: list[dict[str, object]]
    considered: int
    capture: _CaptureSink | None


def _make_tracker(
    trace: TraceSpec, capture_path: Path | None
) -> tuple[SearchTracker, _CaptureSink | None]:
    sink = (
        _CaptureSink(path=capture_path, max_count=trace.capture_all_max)
        if trace.capture_all and capture_path is not None
        else None
    )
    return SearchTracker(samples=trace.samples, capture=sink), sink


def _search_with_tracker(
    task: Task, config: Config, library: Library, tracker: SearchTracker
) -> SearchResult:
    return config.search_engine.run(
        train_examples=task.train,
        library=library,
        constraints=config.constraints,
        cost=config.cost,
        budget=config.budget,
        tracker=tracker,
    )


def _write_trace_artifacts(
    record: RunRecord, trace: TraceSpec, outcomes: Mapping[str, _TrackedOutcome]
) -> None:
    """Write ``samples.jsonl``/``capture/_capture_summary.json`` from *this invocation's*
    freshly-run tasks only — a resumed run's already-traced tasks aren't re-sampled or re-captured
    (``RunRecord.sample_rows``/``capture_summary`` document this as an accepted limitation of a
    diagnostic-only artifact). Each sample row is tagged with its ``task`` label (``task_id``, or
    ``iter-<n>/<task_id>`` for a LEARN wake) since one file holds every task."""
    sample_rows = [
        {"task": label, **row} for label, outcome in outcomes.items() for row in outcome.sample_rows
    ]
    if sample_rows:
        _write_jsonl(record.samples_path, sample_rows)
    if trace.capture_all:
        _write_json(record.capture_summary_path, _capture_summary(trace, outcomes))


def _capture_summary(
    trace: TraceSpec, outcomes: Mapping[str, _TrackedOutcome]
) -> dict[str, object]:
    per_task: dict[str, object] = {}
    captured_total = 0
    truncated = False
    for label, outcome in outcomes.items():
        sink = outcome.capture
        if sink is None:
            continue
        per_task[label] = {
            "considered": outcome.considered,
            "captured": sink.captured,
            "truncated": sink.truncated,
        }
        captured_total += sink.captured
        truncated = truncated or sink.truncated
    return {
        "capture_all_max": trace.capture_all_max,
        "captured_total": captured_total,
        "truncated": truncated,
        "per_task": per_task,
    }


# -- the SEARCH branch ---------------------------------------------------------


def _run_search(run_spec: RunSpec, record: RunRecord, trace: TraceSpec) -> list[dict[str, object]]:
    """Search + predict + score each task, streaming rows to the trace; resume-aware."""
    config = run_spec.config
    rows = _rewrite_trace(record)  # drops any torn final line; returns the intact rows
    done = {row.get("task_id") for row in rows}
    if done:
        logger.info("run %s resuming: %d task(s) served from trace", record.run_id, len(done))

    outcomes: dict[str, _TrackedOutcome] = {}
    with record.trace_path.open("a", encoding="utf-8") as trace_handle:
        for task in run_spec.corpus:
            if task.task_id in done:
                continue
            capture_path = (
                record.capture_dir / f"{task.task_id}.jsonl" if trace.capture_all else None
            )
            row, tracked = _run_task(task, config, trace, capture_path)
            trace_handle.write(json.dumps(row) + "\n")
            trace_handle.flush()  # each completed task is a durable checkpoint
            rows.append(row)
            outcomes[task.task_id] = tracked
    _write_trace_artifacts(record, trace, outcomes)
    return rows


def _predict_and_score(
    task: Task,
    programs: Sequence[Program],
    library: Library,
    *,
    attempts_per_test: int,
) -> tuple[bool, tuple[bool, ...]]:
    """Apply the best programs to ``task``'s test inputs and score them.

    The one place the execution layer touches test grids (via the pure
    ``predict`` + ``score_task``), shared by the SEARCH branch and the
    LEARN branch's per-wake telemetry.
    """
    prediction = predict(
        programs,
        [example.input for example in task.test],
        library,
        attempts_per_test=attempts_per_test,
    )
    return score_task(task, prediction, attempts=attempts_per_test)


def _search_stats(stats: SearchStats) -> dict[str, object]:
    """One task's ``SearchStats`` as the ``search_stats`` block — ``{total, by_primitive}`` —
    shared by the SEARCH branch's per-task row (``_run_task``) and the LEARN branch's per-wake
    per-task rows (``_wake``), so both trace identically (EXECUTION.md). ``total`` = ``considered``
    plus the full funnel-ordered outcome partition (zeros filled); ``by_primitive`` is sparse.
    """
    return {
        "engine": stats.engine,
        "total": {"considered": stats.considered, **stats.outcomes},
        "by_primitive": {key: dict(counts) for key, counts in stats.by_primitive.items()},
    }


def merge_search_stats(
    search_stats: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    """Sum a group of ``_search_stats``-shaped blocks into one ``{total, by_primitive}`` block.

    Shared by ``_search_results`` (across a run's per-task rows) and ``analyze_run`` (across a
    LEARN wake's per-task rows) — both are "merge N search_stats blocks," just over a different
    axis. ``total`` carries the full funnel-ordered outcome set (zeros filled); ``by_primitive``
    stays sparse and primitive-sorted.
    """
    considered = 0
    outcome_totals: dict[str, int] = dict.fromkeys(OUTCOME_NAMES, 0)
    by_primitive: dict[str, dict[str, int]] = {}
    for block in search_stats:
        total = block.get("total")
        if isinstance(total, dict):
            considered += int(total.get("considered", 0) or 0)
            for name in OUTCOME_NAMES:
                value = total.get(name)
                if isinstance(value, int):
                    outcome_totals[name] += value
        primitives = block.get("by_primitive")
        if isinstance(primitives, dict):
            for primitive, counts in primitives.items():
                if not isinstance(counts, dict):
                    continue
                bucket = by_primitive.setdefault(primitive, {})
                for outcome, count in counts.items():
                    if isinstance(count, int):
                        bucket[outcome] = bucket.get(outcome, 0) + count
    return {
        "total": {"considered": considered, **outcome_totals},
        "by_primitive": {
            primitive: funnel_outcomes(by_primitive[primitive], include_zeros=False)
            for primitive in sorted(by_primitive)
        },
    }


def _run_task(
    task: Task, config: Config, trace: TraceSpec, capture_path: Path | None
) -> tuple[dict[str, object], _TrackedOutcome]:
    """One task: search on train examples, predict + score on test examples, tallied."""
    started = time.perf_counter()
    tracker, sink = _make_tracker(trace, capture_path)
    try:
        result = _search_with_tracker(task, config, config.library, tracker)
        solved, per_test = _predict_and_score(
            task,
            result.ranked_programs,
            config.library,
            attempts_per_test=config.attempts_per_test,
        )
        task_result = TaskResult(
            task_id=task.task_id,
            score=TaskScore(solved=solved, per_test=per_test),
            seconds=time.perf_counter() - started,
        )
        search_stats: dict[str, object] | None = _search_stats(result.stats)
        programs = [program.to_dict() for program in result.ranked_programs]
    except Exception as error:  # error isolation: one broken task never aborts the run
        logger.warning("task %s errored: %s", task.task_id, error)
        task_result = TaskResult(
            task_id=task.task_id,
            score=TaskScore(solved=False, per_test=(False,) * len(task.test)),
            seconds=time.perf_counter() - started,
            error=f"{type(error).__name__}: {error}",
        )
        search_stats = None
        programs = []
    finally:
        if sink is not None:
            sink.close()
    row = {**task_result.to_dict(), "programs": programs, "search_stats": search_stats}
    tracked = _TrackedOutcome(
        sample_rows=tracker.sample_rows(), considered=tracker.considered, capture=sink
    )
    return row, tracked


# -- recording -----------------------------------------------------------------


def _rewrite_trace(record: RunRecord) -> list[dict[str, object]]:
    """Load the intact trace rows and rewrite the file to exactly those rows.

    ``trace_rows`` already tolerates a torn final line (a crash mid-write); rewriting
    means the subsequent append never lands after torn bytes. Rows are written unsorted
    (``search_stats`` is emitted in funnel order and must not be re-alphabetized).
    """
    rows = list(record.trace_rows())
    if record.trace_path.is_file():
        with record.trace_path.open("w", encoding="utf-8") as trace_handle:
            for row in rows:
                trace_handle.write(json.dumps(row) + "\n")
    return rows


def _search_results(rows: list[dict[str, object]]) -> dict[str, object]:
    """Aggregate a SEARCH run's task rows into the ``results.json`` payload."""
    tasks = [TaskResult.from_dict(row) for row in rows]
    task_stats = (block for row in rows if isinstance(block := row.get("search_stats"), dict))
    return {
        "task_count": len(tasks),
        "solved": sum(result.score.solved for result in tasks),
        "search_stats": merge_search_stats(task_stats),
        "tasks": [result.to_dict() for result in tasks],
    }


# -- the LEARN branch (the wake-sleep loop; EXECUTION.md) ------------------------


def _run_learn(run_spec: RunSpec, record: RunRecord, trace: TraceSpec) -> dict[str, object]:
    """The wake-sleep loop on the train corpus — ONE recorded run, ending with sleep.

    Per iteration: **wake** (fresh search per task by default; ``reset_programs_each_wake=False``
    carries prior solutions and searches only unsolved tasks) then **sleep**
    (``LearnEngine.run`` over the whole corpus's solutions). Each sleep row carries the grown
    library, so the trace is an iteration-grain checkpoint: resume re-loads the last sleep's
    library and continues. Ends with sleep — the final wake is the derived SEARCH run the
    activity executes afterwards (never evaluate stale programs).
    """
    config = run_spec.config
    learn = config.learn
    assert learn is not None  # the execute() branch guarantees it
    rows = _rewrite_trace(record)

    library = config.library
    solutions: dict[str, SolvedTask] = {}
    start_iteration = 0
    converged = False
    added_names: list[str] = []
    description_length: float | None = None

    last_wake_programs: dict[str, object] = {}
    for row in rows:  # resume: replay the checkpoints (sleep rows carry the library)
        if row.get("phase") == "wake":
            programs = row.get("programs")
            if isinstance(programs, dict):
                last_wake_programs = programs
            continue
        if row.get("phase") != "sleep":
            continue
        library_data = row.get("library")
        if isinstance(library_data, dict):
            library = Library.from_dict(library_data)
        iteration = row.get("iteration")
        start_iteration = int(iteration) + 1 if isinstance(iteration, int) else start_iteration
        converged = bool(row.get("converged", False))
        added = row.get("added")
        if isinstance(added, list):
            added_names.extend(str(name) for name in added)
        dl = row.get("description_length")
        description_length = float(dl) if isinstance(dl, (int, float)) else description_length
    if start_iteration:
        logger.info("run %s resuming from iteration %d", record.run_id, start_iteration)
        if not learn.reset_programs_each_wake and last_wake_programs:
            # carried-solutions semantics survive the resume: rebuild them from the last wake row
            entries = {entry.task.task_id: entry for entry in run_spec.corpus.entries}
            solutions = {
                task_id: SolvedTask(annotated=entries[task_id], program=Program.from_dict(data))
                for task_id, data in last_wake_programs.items()
                if task_id in entries and isinstance(data, dict)
            }

    iterations_run = start_iteration
    all_outcomes: dict[str, _TrackedOutcome] = {}
    with record.trace_path.open("a", encoding="utf-8") as trace_handle:
        for iteration in range(start_iteration, learn.iterations):
            if converged and learn.early_stop:
                break
            # WAKE — batched over the whole corpus before any sleep (cross-task compression).
            if learn.reset_programs_each_wake:
                solutions = {}
            wake_row, wake_outcomes = _wake(run_spec, library, solutions, iteration, record, trace)
            for task_id, tracked in wake_outcomes.items():
                all_outcomes[f"iter-{iteration}/{task_id}"] = tracked
            trace_handle.write(json.dumps(wake_row) + "\n")
            trace_handle.flush()
            # SLEEP — one LearnEngine.run over all solutions.
            outcome = learn.learn_engine.run(library, tuple(solutions.values()))
            library = outcome.library
            converged = outcome.converged
            added_names.extend(primitive.name for primitive in outcome.added)
            description_length = outcome.description_length
            sleep_row = {
                "iteration": iteration,
                "phase": "sleep",
                "added": [primitive.name for primitive in outcome.added],
                "description_length": outcome.description_length,
                "converged": outcome.converged,
                "library": library.to_dict(),  # the checkpoint resume reads
            }
            trace_handle.write(json.dumps(sleep_row) + "\n")
            trace_handle.flush()
            iterations_run = iteration + 1

    _write_json(record.learned_library_path, library.to_dict())
    _write_trace_artifacts(record, trace, all_outcomes)
    return {
        "iterations_run": iterations_run,
        "converged": converged,
        "added": added_names,
        "description_length": description_length,
        "library_size": len(library.primitives),
        "library_version": library.version,
    }


def _wake(
    run_spec: RunSpec,
    library: Library,
    solutions: dict[str, SolvedTask],
    iteration: int,
    record: RunRecord,
    trace: TraceSpec,
) -> tuple[dict[str, object], dict[str, _TrackedOutcome]]:
    """One wake: search every (not-yet-carried) task with the current library; mutate ``solutions``.

    Per-task stats are recorded in the same shape as the SEARCH branch's trace rows
    (``_search_stats``), so a wake traces identically to a SEARCH run — including the
    per-primitive/node-kind breakdown, e.g. to see whether a sleep-minted primitive gets used in
    the very next wake. Returns the wake row (for the trace) plus this wake's per-task
    ``_TrackedOutcome``s (for the run-wide samples/capture-summary, keyed by the caller).
    """
    config = run_spec.config
    learn = config.learn
    assert learn is not None
    considered = 0
    search_stats: dict[str, object] = {}
    scores: dict[str, bool] = {}
    outcomes: dict[str, _TrackedOutcome] = {}
    for entry in run_spec.corpus.entries:  # entries: SolvedTask keeps meta co-located
        task = entry.task
        if task.task_id in solutions:  # only when reset_programs_each_wake=False
            continue
        capture_path = (
            record.capture_dir / f"iter-{iteration}" / f"{task.task_id}.jsonl"
            if trace.capture_all
            else None
        )
        tracker, sink = _make_tracker(trace, capture_path)
        result = _search_with_tracker(task, config, library, tracker)
        if sink is not None:
            sink.close()
        considered += result.stats.considered
        search_stats[task.task_id] = _search_stats(result.stats)
        outcomes[task.task_id] = _TrackedOutcome(
            sample_rows=tracker.sample_rows(), considered=tracker.considered, capture=sink
        )
        if result.ranked_programs:
            solutions[task.task_id] = SolvedTask(annotated=entry, program=result.ranked_programs[0])
        if learn.score_each_wake and task.test:  # telemetry only; never feeds back
            solved, _ = _predict_and_score(
                task,
                result.ranked_programs,
                library,
                attempts_per_test=config.attempts_per_test,
            )
            scores[task.task_id] = solved
    wake_row: dict[str, object] = {
        "iteration": iteration,
        "phase": "wake",
        "solved": sorted(solutions),
        "considered": considered,
        "search_stats": search_stats,
        "programs": {task_id: st.program.to_dict() for task_id, st in solutions.items()},
    }
    if scores:
        wake_row["scores"] = scores
    return wake_row, outcomes


def _write_json(path: Path, data: Mapping[str, object]) -> None:
    """Write ``data`` as pretty JSON in *insertion* order — funnel-ordered stats blocks must not
    be re-alphabetized. Deterministic anyway (no RNG; every dict is built deterministically), and
    run identity is hashed separately (``core/hashing.py``), so key order here is free."""
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """Write ``rows`` one compact JSON object per line (insertion order preserved)."""
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _current_commit() -> str | None:
    """The current git commit — provenance only, never part of the ``run_id`` hash."""
    try:
        output = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return output.stdout.strip() or None


def _now_iso() -> str:
    """Wall-clock run start — provenance only, never part of the ``run_id`` hash."""
    return datetime.now(UTC).isoformat()


def _timestamp() -> str:
    """A sortable dirname prefix — pairs with ``run_id`` as ``<timestamp>_<run_id>``."""
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
