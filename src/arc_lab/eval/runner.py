"""Run a solver over a dataset and collect a scored report.

The runner is deliberately solver-agnostic: it calls ``solver.predict`` on each
task, scores the result, records timing, and isolates failures so one broken
task never aborts the whole run.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from arc_lab.core.dataset import Dataset
from arc_lab.core.task import Task
from arc_lab.eval.scoring import score_task
from arc_lab.solvers.base import Solver


@dataclass(frozen=True, slots=True)
class TaskResult:
    """The outcome of running one solver on one task."""

    task_id: str
    solved: bool
    per_test: tuple[bool, ...]
    seconds: float
    error: str | None = None


@dataclass(frozen=True, slots=True)
class Report:
    """Aggregate results of a run."""

    solver: str
    dataset: str
    results: tuple[TaskResult, ...] = field(default_factory=tuple)

    @property
    def solved(self) -> int:
        return sum(r.solved for r in self.results)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def errored(self) -> int:
        return sum(r.error is not None for r in self.results)

    @property
    def accuracy(self) -> float:
        return self.solved / self.total if self.total else 0.0

    @property
    def seconds(self) -> float:
        return sum(r.seconds for r in self.results)

    def summary(self) -> str:
        pct = f"{self.accuracy:.1%}"
        line = f"{self.solver} on {self.dataset}: {self.solved}/{self.total} solved ({pct})"
        if self.errored:
            line += f", {self.errored} errored"
        line += f" in {self.seconds:.1f}s"
        return line


def _run_one(solver: Solver, task: Task) -> TaskResult:
    start = time.perf_counter()
    try:
        prediction = solver.predict(task)
        solved, per_test = score_task(task, prediction)
        return TaskResult(
            task_id=task.task_id,
            solved=solved,
            per_test=per_test,
            seconds=time.perf_counter() - start,
        )
    except Exception as exc:
        return TaskResult(
            task_id=task.task_id,
            solved=False,
            per_test=(),
            seconds=time.perf_counter() - start,
            error=f"{type(exc).__name__}: {exc}",
        )


def run(
    solver: Solver,
    dataset: Dataset,
    *,
    progress: bool = False,
) -> Report:
    """Run ``solver`` over every task in ``dataset`` and return a scored report."""
    results: list[TaskResult] = []
    for i, task in enumerate(dataset, start=1):
        result = _run_one(solver, task)
        results.append(result)
        if progress:
            mark = "x" if result.error else ("O" if result.solved else ".")
            print(mark, end="", flush=True)
            if i % 50 == 0:
                print(f"  {i}/{len(dataset)}", flush=True)
    if progress:
        print(flush=True)
    return Report(solver=solver.name, dataset=dataset.name, results=tuple(results))
