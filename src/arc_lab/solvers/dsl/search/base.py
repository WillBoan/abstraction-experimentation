"""The search-strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.program import Program


class Search(ABC):
    """Find candidate programs for a task, best (most preferred) first.

    Implementations decide how to use the task's training examples — typically to
    filter or rank candidates by consistency — and return the programs a solver
    should try, in priority order.
    """

    @abstractmethod
    def find(self, task: Task, library: Library) -> list[Program]:
        """Return ranked candidate programs for ``task`` over ``library``."""
