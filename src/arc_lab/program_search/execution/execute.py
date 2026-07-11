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
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Final

from arc_lab.core.task import Task
from arc_lab.eval.scoring import score_task
from arc_lab.program_search.analysis.compression import SolvedTask
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Program

from .model.config import Config
from .model.results import TaskResult, TaskScore
from .model.run_record import RunRecord
from .model.run_spec import RunSpec
from .predict import predict

logger = logging.getLogger(__name__)

#: Repo-root ``runs/`` — the gitignored, regenerable artifact cache.
DEFAULT_RUNS_ROOT: Final = Path(__file__).resolve().parents[4] / "runs"


def execute(run_spec: RunSpec, *, runs_root: Path | None = None) -> RunRecord:
    """Execute (or serve from cache) the recorded run ``run_spec`` names."""
    root = DEFAULT_RUNS_ROOT if runs_root is None else runs_root
    record = RunRecord(run_id=run_spec.run_id, run_dir=root / run_spec.run_id)

    if record.completed:  # idempotency: results.json present ⇒ cached
        logger.info("run %s served from cache (%s)", record.run_id, record.run_dir)
        return record

    record.run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(record.runspec_path, {**run_spec.to_dict(), "commit": _current_commit()})

    if run_spec.config.learn is None:
        payload = _search_results(_run_search(run_spec, record))
    else:
        payload = _run_learn(run_spec, record)

    _write_json(
        record.results_path,  # the LAST write — its presence marks the run complete
        {"run_id": record.run_id, "corpus_name": run_spec.corpus.name, **payload},
    )
    logger.info("run %s recorded to %s", record.run_id, record.run_dir)
    return record


# -- the SEARCH branch ---------------------------------------------------------


def _run_search(run_spec: RunSpec, record: RunRecord) -> list[dict[str, object]]:
    """Search + predict + score each task, streaming rows to the trace; resume-aware."""
    config = run_spec.config
    rows = _rewrite_trace(record)  # drops any torn final line; returns the intact rows
    done = {row.get("task_id") for row in rows}
    if done:
        logger.info("run %s resuming: %d task(s) served from trace", record.run_id, len(done))

    with record.trace_path.open("a", encoding="utf-8") as trace:
        for task in run_spec.corpus:
            if task.task_id in done:
                continue
            row = _run_task(task, config)
            trace.write(json.dumps(row, sort_keys=True) + "\n")
            trace.flush()  # each completed task is a durable checkpoint
            rows.append(row)
    return rows


def _run_task(task: Task, config: Config) -> dict[str, object]:
    """One task: search on train examples, predict + score on test examples, tallied."""
    started = time.perf_counter()
    try:
        result = config.search_engine.run(
            train_examples=task.train,
            library=config.library,
            constraints=config.constraints,
            cost=config.cost,
        )
        prediction = predict(
            result.ranked_programs,
            [example.input for example in task.test],
            config.library,
            attempts_per_test=config.attempts_per_test,
        )
        solved, per_test = score_task(task, prediction, attempts=config.attempts_per_test)
        task_result = TaskResult(
            task_id=task.task_id,
            score=TaskScore(solved=solved, per_test=per_test),
            seconds=time.perf_counter() - started,
        )
        stats: dict[str, object] | None = {
            "engine": result.stats.engine,
            "considered": result.stats.considered,
            "accepted": result.stats.accepted,
            "extra": dict(result.stats.extra),
        }
        programs = [program.to_dict() for program in result.ranked_programs]
    except Exception as error:  # error isolation: one broken task never aborts the run
        logger.warning("task %s errored: %s", task.task_id, error)
        task_result = TaskResult(
            task_id=task.task_id,
            score=TaskScore(solved=False, per_test=(False,) * len(task.test)),
            seconds=time.perf_counter() - started,
            error=f"{type(error).__name__}: {error}",
        )
        stats = None
        programs = []
    return {**task_result.to_dict(), "programs": programs, "stats": stats}


# -- recording -----------------------------------------------------------------


def _rewrite_trace(record: RunRecord) -> list[dict[str, object]]:
    """Load the intact trace rows and rewrite the file to exactly those rows.

    ``trace_rows`` already tolerates a torn final line (a crash mid-write); rewriting
    means the subsequent append never lands after torn bytes.
    """
    rows = list(record.trace_rows())
    if record.trace_path.is_file():
        with record.trace_path.open("w", encoding="utf-8") as trace:
            for row in rows:
                trace.write(json.dumps(row, sort_keys=True) + "\n")
    return rows


def _search_results(rows: list[dict[str, object]]) -> dict[str, object]:
    """Aggregate a SEARCH run's task rows into the ``results.json`` payload."""
    tasks = [TaskResult.from_dict(row) for row in rows]
    considered = sum(
        int(stats["considered"])
        for row in rows
        if isinstance(stats := row.get("stats"), dict) and "considered" in stats
    )
    return {
        "task_count": len(tasks),
        "solved": sum(result.score.solved for result in tasks),
        "considered_total": considered,
        "tasks": [result.to_dict() for result in tasks],
    }


# -- the LEARN branch (the wake-sleep loop; EXECUTION.md) ------------------------


def _run_learn(run_spec: RunSpec, record: RunRecord) -> dict[str, object]:
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
    with record.trace_path.open("a", encoding="utf-8") as trace:
        for iteration in range(start_iteration, learn.iterations):
            if converged and learn.early_stop:
                break
            # WAKE — batched over the whole corpus before any sleep (cross-task compression).
            if learn.reset_programs_each_wake:
                solutions = {}
            wake_row = _wake(run_spec, library, solutions, iteration)
            trace.write(json.dumps(wake_row, sort_keys=True) + "\n")
            trace.flush()
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
            trace.write(json.dumps(sleep_row, sort_keys=True) + "\n")
            trace.flush()
            iterations_run = iteration + 1

    _write_json(record.learned_library_path, library.to_dict())
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
) -> dict[str, object]:
    """One wake: search every (not-yet-carried) task with the current library; mutate ``solutions``."""
    config = run_spec.config
    learn = config.learn
    assert learn is not None
    considered = 0
    scores: dict[str, bool] = {}
    for entry in run_spec.corpus.entries:  # entries: SolvedTask keeps meta co-located
        task = entry.task
        if task.task_id in solutions:  # only when reset_programs_each_wake=False
            continue
        result = config.search_engine.run(
            train_examples=task.train,
            library=library,
            constraints=config.constraints,
            cost=config.cost,
        )
        considered += result.stats.considered
        if result.ranked_programs:
            solutions[task.task_id] = SolvedTask(annotated=entry, program=result.ranked_programs[0])
        if learn.score_each_wake and task.test:  # telemetry only; never feeds back
            prediction = predict(
                result.ranked_programs,
                [example.input for example in task.test],
                library,
                attempts_per_test=config.attempts_per_test,
            )
            solved, _ = score_task(task, prediction, attempts=config.attempts_per_test)
            scores[task.task_id] = solved
    wake_row: dict[str, object] = {
        "iteration": iteration,
        "phase": "wake",
        "solved": sorted(solutions),
        "considered": considered,
        "programs": {task_id: st.program.to_dict() for task_id, st in solutions.items()},
    }
    if scores:
        wake_row["scores"] = scores
    return wake_row


def _write_json(path: Path, data: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")


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
