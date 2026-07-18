from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from ..substrate.program import Program
from .tracking import SolutionRecord


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
    by_primitive: Mapping[str, Mapping[str, int]] = field(default_factory=dict)
    #: The composition round (``PoolEntry.generation``, ``search/search_engine.py``) the accepted
    #: solution was first built at — ``None`` if unsolved. Round 0 is the leaf round (matching
    #: ``Budget.max_depth``'s own accounting, ``execution/presets.py``). A per-task diagnostic for
    #: budget calibration (e.g. solutions clustering near ``max_depth`` suggests raising it might
    #: solve more; clustering well below it suggests the budget has room to shrink) — never part of
    #: the outcome partition, and not meaningful to sum across tasks (``merge_search_stats`` in
    #: ``execution/execute.py`` deliberately leaves it out of the corpus-wide aggregate).
    solved_at_generation: int | None = None
    #: The per-round funnel (``SearchTracker.generations()``): pool sizes + where every candidate
    #: newly absorbed each round ended up. Top-level rounds only; per-task (like
    #: ``solved_at_generation``, kept out of ``merge_search_stats``). The source for ``b_eff``.
    generations: tuple[Mapping[str, int | None], ...] = ()
    #: Solution-sink telemetry (``search/tracking.py``): every goal-matching candidate seen at
    #: absorption, before the pool's dedup collapses them to one. Dormant here — the returned
    #: ``ranked_programs`` and ``.solved`` are still pool-based (a later commit makes them
    #: sink-based). ``first_solution_index`` / ``cheapest_solution_index`` stay exact under the cap;
    #: ``solution_count`` / ``solutions`` degrade (with ``solutions_truncated`` loud) if it binds.
    first_solution_index: int | None = None
    cheapest_solution_index: int | None = None
    solution_count: int = 0
    solutions_truncated: bool = False
    solutions: tuple[SolutionRecord, ...] = ()

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
        if self.solved_at_generation is not None:
            parts.append(f"solved_at_generation={self.solved_at_generation}")
        return f"{self.engine}: " + " ".join(parts)
