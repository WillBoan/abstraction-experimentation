"""Constraints: the *filter* step of program search.

A :class:`Constraint` is a boolean acceptance criterion a candidate program must
pass. Constraints compose — a search accepts a program only if *every* active
constraint holds — and a strategy may apply them as a final acceptance test or as
a mid-search pruning signal, whichever fits.

:class:`ConsistentWithTraining` is the load-bearing one: it is the *specification*
derived from the data (a program that fails it is simply wrong).

In future, we may add inductive-bias constraints alongside it.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arc_lab.core.task import Task
    from arc_lab.solvers.dsl.substrate.library import Library
    from arc_lab.solvers.dsl.substrate.program import Program

logger = logging.getLogger(__name__)


class Constraint(ABC):
    """A predicate a candidate program must satisfy to be accepted."""

    @abstractmethod
    def holds(self, program: Program, task: Task, library: Library) -> bool:
        """True if ``program`` satisfies this constraint for ``task``."""


class ConsistentWithTraining(Constraint):
    """Accept a program iff it reproduces the output of every *training* example."""

    def holds(self, program: Program, task: Task, library: Library) -> bool:
        for i, example in enumerate(task.train):
            if example.output is None:
                return False
            produced = program.evaluate_grid(example.input, library)
            if produced != example.output:
                logger.debug(
                    "inconsistent %s at train[%d]: got %r want %r",
                    program,
                    i,
                    produced,
                    example.output,
                )
                return False
        return True
