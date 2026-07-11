"""Costs: the *rank* step of program search.

A :class:`Cost` scores a program -- **lower is better** -- so candidates can be
ordered (and, later, search guided). Costs compose by summation: program size (an
Occam prior) and a future learned prior (as -log P) are both costs, added together
-- which is the minimum-description-length view of "simple *and* likely".

The signature includes ``train_examples`` and ``library`` even though a purely
structural cost like :class:`ProgramSize` ignores them, so that data-dependent
costs (partial credit, likelihood) share the same interface. Costs receive the
task's *train examples only* -- ranking is train-side machinery, structurally
blind to test grids (EXECUTION.md, Sync B).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arc_lab.core.task import TrainExamples
    from arc_lab.program_search.substrate.library import Library
    from arc_lab.program_search.substrate.program import Program


class Cost(ABC):
    """A ranking signal over programs; lower is better.

    Concrete costs are frozen dataclasses: a ``Cost`` is run identity (it sits in
    ``Config`` and inside ``CompressionMetric``), so it must serialise via the
    component serde and compare by value.
    """

    @abstractmethod
    def of(self, program: Program, train_examples: TrainExamples, library: Library) -> float:
        """The cost of ``program`` (lower ranks earlier)."""


@dataclass(frozen=True, slots=True)
class ProgramSize(Cost):
    """An Occam prior: prefer programs with fewer nodes."""

    def of(self, program: Program, train_examples: TrainExamples, library: Library) -> float:
        return float(program.size())
