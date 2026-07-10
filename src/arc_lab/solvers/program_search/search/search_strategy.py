from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from arc_lab.core.task import Task

from ..substrate.library import Library
from ..substrate.program import Program
from .constraints import ConsistentWithTraining, Constraint


@dataclass(frozen=True, slots=True)
class SearchStats:
    """Standardised, structured tally of one search `find` call.

    Every strategy reports the same two core counters so they compose and compare:

    * ``considered`` — how many candidate programs the strategy examined. This is the
      raw "search effort" signal a speedup metric reads (fewer considered for the same
      solve = a cheaper search).
    * ``accepted`` — how many candidate programs the strategy handed back.

    Strategy-specific counters (if needed) live in `extra`, so the common shape stays uniform
    for consumers.

    Formatting is centralised in :meth:`summary`.
    """

    strategy: str
    considered: int = 0
    accepted: int = 0
    extra: Mapping[str, int] = field(default_factory=dict)

    @property
    def solved(self) -> bool:
        """True if the strategy returned at least one (train-consistent) program.

        Note this is *search*-level success (a program consistent with the training
        pairs was found), not *test*-set correctness — that is the scorer's verdict.
        """
        return self.accepted > 0

    def summary(self) -> str:
        """The one-line INFO summary, derived from the counters."""
        parts = [f"considered={self.considered}", f"accepted={self.accepted}"]
        parts += [f"{key}={value}" for key, value in self.extra.items()]
        parts.append(f"solved={self.solved}")
        return f"{self.strategy}: " + " ".join(parts)


@dataclass(frozen=True, slots=True)
class SearchResult:
    """What a :meth:`Search.find` returns: ranked programs plus the run's stats."""

    accepted_programs: tuple[Program, ...]
    stats: SearchStats


class SearchStrategy(ABC):
    """
    A search strategy is a pluggable component that implements the program search algorithm.
    """

    def __init__(
        self,
        *,
        constraints: Sequence[Constraint] | None = None,
    ) -> None:
        self.constraints: tuple[Constraint, ...] = (
            (ConsistentWithTraining(),) if constraints is None else tuple(constraints)
        )

    def all_constraints_hold(self, program: Program, task: Task, library: Library) -> bool:
        """True if ``program`` satisfies every active constraint."""
        return all(constraint.holds(program, task, library) for constraint in self.constraints)

    @abstractmethod
    def find(self, task: Task, library: Library) -> SearchResult:
        """Find candidate programs for a task, best first."""
