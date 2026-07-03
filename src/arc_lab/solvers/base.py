"""The solver interface — the one contract the whole harness is built around.

A solver looks at a :class:`~arc_lab.core.task.Task` and, for each test input,
proposes a *ranked* list of candidate output grids. ARC scoring allows two
attempts per test input, so the harness takes the top two candidates; returning
more is harmless (they are ignored) and returning fewer is fine too.

Keeping this contract deliberately narrow is what lets LLM solvers, DSL search
solvers, neural solvers, and anything else coexist without the scorer, runner,
or CLI knowing which is which.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task

# For each test input, a ranked list of candidate outputs (best first).
Prediction = list[list[Grid]]


class Solver(ABC):
    """Abstract base class for all solvers."""

    #: Short, stable identifier used in reports and the CLI.
    name: str = "solver"

    @abstractmethod
    def predict(self, task: Task) -> Prediction:
        """Return candidate outputs for each test input in ``task``.

        The returned list must be aligned with ``task.test``: element *i* is the
        ranked list of candidate grids for ``task.test[i]``.
        """

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"


def constant_prediction(task: Task, grid: Grid) -> Prediction:
    """Helper: predict the same single ``grid`` for every test input."""
    return [[grid] for _ in task.test]
