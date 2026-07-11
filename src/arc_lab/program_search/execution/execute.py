"""``execute``: the recorded-run core — the ONLY writer of ``runs/`` (EXECUTION.md).

One ``execute(run_spec)`` = one recorded run, addressed by ``run_id``:

- **Idempotent** — a present ``results.json`` is served from cache, no execution.
- **Crash-safe** — ``runspec.json`` is written *first* (identity survives a crash);
  ``results.json`` is written *last* (its presence marks completion).
- **Resumable** — per-task rows stream to ``trace.jsonl`` as they finish; on restart,
  already-traced tasks are served from the trace and only the remainder runs.
- **Isolated** — one broken task never aborts the run: its row records the error and
  an all-False score.

``config.learn is None`` ⇒ the SEARCH branch (below). ``config.learn`` set ⇒ the
LEARN branch (the wake-sleep loop) — lands with the activities phase (Sync C:
concrete ``LearnEngine``s pending).
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
        rows = _run_search(run_spec, record)
    else:
        raise NotImplementedError(
            "LEARN runs land with the activities phase (Sync C: concrete LearnEngines pending)"
        )

    _write_results(run_spec, record, rows)
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


def _write_results(run_spec: RunSpec, record: RunRecord, rows: list[dict[str, object]]) -> None:
    """Aggregate the rows and write ``results.json`` — the LAST write (completion marker)."""
    tasks = [TaskResult.from_dict(row) for row in rows]
    considered = sum(
        int(stats["considered"])
        for row in rows
        if isinstance(stats := row.get("stats"), dict) and "considered" in stats
    )
    _write_json(
        record.results_path,
        {
            "run_id": record.run_id,
            "corpus_name": run_spec.corpus.name,
            "task_count": len(tasks),
            "solved": sum(result.score.solved for result in tasks),
            "considered_total": considered,
            "tasks": [result.to_dict() for result in tasks],
        },
    )


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
