"""Constraints: *extra* inductive-bias filters on goal-test survivors.

A :class:`Constraint` is NOT the consistency check. Consistency-with-training is the
engine's goal test itself — ``sig == target`` in ``extraction.py``, read from the
signature the pool already cached for dedup — the *definition* of a solution, not a
filter on one. (A ``Constraint`` reimplementation of it would also be wrong: a fresh
``evaluate`` crashes on the partial-⊥ programs the pool deliberately tolerates for
domain-splitting ``if``.)

What lives here instead: genuinely *extra* acceptance criteria that need information
signature equality cannot provide — e.g. "the output must be square", or a shape
prior. Constraints compose by conjunction (a program passes iff *every* active
constraint holds) and run **after** the goal test, on survivors only — an
implementation may therefore assume it receives train-consistent programs. The
default is no constraints (``Config.constraints = ()``).

Constraints receive the task's *train examples only* — they are train-side
machinery, structurally blind to test grids, like ``Cost.of`` (EXECUTION.md, Sync B).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arc_lab.core.task import TrainExamples
    from arc_lab.program_search.substrate.library import Library
    from arc_lab.program_search.substrate.program import Program


class Constraint(ABC):
    """An extra acceptance predicate, applied to programs that already pass the goal test."""

    @abstractmethod
    def holds(self, program: Program, train_examples: TrainExamples, library: Library) -> bool:
        """True if ``program`` satisfies this constraint for the task's train examples."""
