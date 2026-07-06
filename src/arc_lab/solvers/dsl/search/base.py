"""The search-strategy interface.

A :class:`Search` is the *propose* step: it turns a task + library into ranked
candidate programs. It is configured with a set of :class:`Constraint`\\ s (the
*filter* step; default: consistency with the training examples) and applies them
via :meth:`accepts` — as a final acceptance test or a mid-search pruning signal,
whichever fits the strategy.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search.constraints import ConsistentWithTraining, Constraint
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.program import Program


class Search(ABC):
    """Find candidate programs for a task, best (most preferred) first."""

    def __init__(self, *, constraints: Sequence[Constraint] | None = None) -> None:
        self.constraints: tuple[Constraint, ...] = (
            (ConsistentWithTraining(),) if constraints is None else tuple(constraints)
        )

    def accepts(self, program: Program, task: Task, library: Library) -> bool:
        """True if ``program`` satisfies every active constraint."""
        return all(constraint.holds(program, task, library) for constraint in self.constraints)

    @abstractmethod
    def find(self, task: Task, library: Library) -> list[Program]:
        """Return ranked candidate programs for ``task`` over ``library``."""
