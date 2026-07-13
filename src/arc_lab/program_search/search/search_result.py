from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from ..substrate.program import Program


@dataclass(frozen=True, slots=True)
class SearchResult:
    """What a :meth:`SearchEngine.run` returns: ranked programs plus the run's stats."""

    ranked_programs: tuple[Program, ...]
    stats: SearchStats


@dataclass(frozen=True, slots=True)
class SearchStats:
    engine: str
    considered: int = 0
    accepted: int = 0
    #: The full outcome partition (capability tracking, ``search/tracking.py``): the invariant
    #: ``considered == sum(outcomes.values())`` holds exactly, including an ``"accepted"`` entry
    #: that mirrors the ``accepted`` field above — kept both places so ``outcomes`` alone is a
    #: complete, self-checking partition while ``accepted`` stays for existing callers.
    outcomes: Mapping[str, int] = field(default_factory=dict)
    #: The same outcome counts, broken down per primitive-name / node-kind key.
    by_key: Mapping[str, Mapping[str, int]] = field(default_factory=dict)

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
        parts += [f"{key}={value}" for key, value in self.outcomes.items() if key != "accepted"]
        parts.append(f"solved={self.solved}")
        return f"{self.engine}: " + " ".join(parts)
