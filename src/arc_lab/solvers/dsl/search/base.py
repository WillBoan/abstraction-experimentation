"""The search-strategy interface.

A :class:`Search` is the *propose* step: it turns a task + library into ranked
candidate programs. It is configured with a set of :class:`Constraint`\\ s (the
*filter* step; default: consistency with the training examples) and applies them
via :meth:`accepts` — as a final acceptance test or a mid-search pruning signal,
whichever fits the strategy.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search.constraints import ConsistentWithTraining, Constraint
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.program import Program


@dataclass(frozen=True, slots=True)
class SearchStats:
    """Standardised, structured tally of one search run — the *data* behind the trace.

    Every strategy reports the same two core counters so they compose and compare:

    * ``considered`` — how many candidate programs the strategy examined. This is the
      raw "search effort" signal a speedup metric reads (fewer considered for the same
      solve = a cheaper search).
    * ``returned`` — how many candidate programs the strategy handed back.

    Strategy-specific counters (Enumerate's dedup tallies, Overlay's skips, …) live in
    ``extra`` so the common shape stays uniform for consumers (metrics, the run trace)
    while nothing is lost. Formatting is centralised in :meth:`summary` so the INFO log
    line is derived from this record rather than hand-rolled per strategy.
    """

    strategy: str
    considered: int = 0
    returned: int = 0
    extra: Mapping[str, int] = field(default_factory=dict)

    @property
    def solved(self) -> bool:
        """True if the strategy returned at least one (train-consistent) program.

        Note this is *search*-level success (a program consistent with the training
        pairs was found), not test-set correctness — that is the scorer's verdict.
        """
        return self.returned > 0

    def summary(self) -> str:
        """The one-line INFO summary, derived from the counters (single source of truth)."""
        parts = [f"considered={self.considered}", f"returned={self.returned}"]
        parts += [f"{key}={value}" for key, value in self.extra.items()]
        parts.append(f"solved={self.solved}")
        return f"{self.strategy}: " + " ".join(parts)


@dataclass(frozen=True, slots=True)
class SearchResult:
    """What a :meth:`Search.find` returns: ranked programs plus the run's stats."""

    programs: tuple[Program, ...]
    stats: SearchStats


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
    def find(self, task: Task, library: Library) -> SearchResult:
        """Return ranked candidate programs (best first) plus the run's :class:`SearchStats`."""
