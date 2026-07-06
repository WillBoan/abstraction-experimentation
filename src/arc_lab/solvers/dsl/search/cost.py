"""Costs: the *rank* step of program search.

A :class:`Cost` scores a program -- **lower is better** -- so candidates can be
ordered (and, later, search guided). Costs compose by summation: program size (an
Occam prior) and a future learned prior (as -log P) are both costs, added together
-- which is the minimum-description-length view of "simple *and* likely".

The signature includes ``task`` and ``library`` even though a purely structural
cost like :class:`ProgramSize` ignores them, so that data-dependent costs
(partial credit, likelihood) share the same interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arc_lab.core.task import Task
    from arc_lab.solvers.dsl.substrate.library import Library
    from arc_lab.solvers.dsl.substrate.program import Program


class Cost(ABC):
    """A ranking signal over programs; lower is better."""

    @abstractmethod
    def of(self, program: Program, task: Task, library: Library) -> float:
        """The cost of ``program`` (lower ranks earlier)."""


class ProgramSize(Cost):
    """An Occam prior: prefer programs with fewer nodes."""

    def of(self, program: Program, task: Task, library: Library) -> float:
        return float(program.size())
