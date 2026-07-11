"""ARC scoring rules — paradigm-agnostic (grids in, booleans out).

Under the official ARC-AGI rules a solver gets **two attempts** per test input,
and a test input counts as correct if either attempt exactly matches the ground
truth. A *task* is solved only if **every** one of its test inputs is correct.

The attempt count is a parameter (``attempts``, default the official 2) because it
is part of a run's identity — solve-rate depends on it — and flows from
``Config.attempts_per_test``. These functions stay pure and solver-agnostic: they
compare grids, nothing else. ``predict`` (building the candidate grids from found
programs) lives in ``program_search/execution/``.
"""

from __future__ import annotations

from typing import Final, TypeAlias

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task

#: Per test input, the candidate output grids, best first.
Prediction: TypeAlias = list[list[Grid]]

#: Attempts allowed per test input under the official ARC rule — the default ``attempts``.
MAX_ATTEMPTS: Final = 2


def score_test_input(candidates: list[Grid], target: Grid, *, attempts: int = MAX_ATTEMPTS) -> bool:
    """True if any of the top-``attempts`` candidates matches ``target``."""
    return any(candidate == target for candidate in candidates[:attempts])


def score_task(
    task: Task, prediction: Prediction, *, attempts: int = MAX_ATTEMPTS
) -> tuple[bool, tuple[bool, ...]]:
    """Score a full task.

    Returns ``(solved, per_test)`` where ``per_test[i]`` is whether test input
    *i* was answered correctly. Raises if the task has no ground-truth outputs
    (i.e. a hidden test set), which cannot be scored locally.
    """
    targets = task.test_outputs
    if targets is None:
        raise ValueError(f"task {task.task_id!r} has no ground-truth outputs to score against")
    if len(prediction) != len(targets):
        raise ValueError(
            f"prediction has {len(prediction)} entries but task {task.task_id!r} "
            f"has {len(targets)} test inputs"
        )
    per_test = tuple(
        score_test_input(candidates, target, attempts=attempts)
        for candidates, target in zip(prediction, targets, strict=True)
    )
    return all(per_test), per_test
