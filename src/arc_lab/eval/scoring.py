"""ARC scoring rules.

Under the official ARC-AGI rules a solver gets **two attempts** per test input,
and a test input counts as correct if either attempt exactly matches the ground
truth. A *task* is solved only if **every** one of its test inputs is correct.
"""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.solvers.base import Prediction

#: Number of attempts allowed per test input (official ARC rule).
MAX_ATTEMPTS = 2


def score_test_input(candidates: list[Grid], target: Grid) -> bool:
    """True if any of the top-``MAX_ATTEMPTS`` candidates matches ``target``."""
    return any(candidate == target for candidate in candidates[:MAX_ATTEMPTS])


def score_task(task: Task, prediction: Prediction) -> tuple[bool, tuple[bool, ...]]:
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
        score_test_input(candidates, target)
        for candidates, target in zip(prediction, targets, strict=True)
    )
    return all(per_test), per_test
