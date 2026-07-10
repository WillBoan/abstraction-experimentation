"""The bottom-up search engine (sections 4-5 of ARCHITECTURE.md).

A ``SearchEngine`` is frozen configuration: its capability policies and its ``Budget``. A single
``run`` builds the full typed pool bottom-up (``_enumerate``) and then reads solutions off it
(``extract``, §5.8). Per-run mutable scratch — the effort tally and the fresh-type-variable counter —
lives in ``_RunState`` so the engine itself stays immutable and reusable across runs.

This is the first-order closed-term core. Variadic composition (§5.2), higher-order fill (§5.3),
short-circuit ``If`` (§5.4), and the polymorphism-instantiation policy (§6.2) layer onto this spine.
"""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from arc_lab.core.task import Task

from ..substrate.library import Library
from ..substrate.program import Program
from ..substrate.types import GRID, Type
from .budget import Budget
from .composition import first_order_applications
from .constraints import Constraint
from .context import Context
from .cost import Cost
from .extraction import extract
from .leaves import ConstantSource, seed_leaves
from .pool import Pool
from .scope import Scope
from .search_result import SearchResult, SearchStats
from .signature import Signature, compute_signature, signature_matches_type

FunctionHoleFillMode: TypeAlias = Literal["none", "point-free", "lambda-synthesis"]
PolymorphismInstantiation: TypeAlias = Literal["monomorphize", "bounded", "unrestricted"]


@dataclass(slots=True)
class _Tally:
    """Search-effort counters, accumulated during a run and frozen into ``SearchStats``."""

    considered: int = 0
    errored: int = 0
    pruned: int = 0
    deduped: int = 0

    def as_extra(self) -> dict[str, int]:
        return {"errored": self.errored, "pruned": self.pruned, "deduped": self.deduped}


@dataclass(slots=True)
class _RunState:
    """The inputs and mutable scratch of a single ``run`` — never part of the memoization key (§9)."""

    task: Task
    library: Library
    cost: Cost
    tally: _Tally = field(default_factory=_Tally)
    counter: itertools.count[int] = field(default_factory=itertools.count)


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchEngine(ABC):
    """The reusable machinery that performs a program search."""

    @abstractmethod
    def run(
        self,
        *,
        task: Task,
        library: Library,
        constraints: tuple[Constraint, ...],
        cost: Cost,
    ) -> SearchResult:
        """Search for programs solving ``task``, ranked cheapest-first."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BottomUpSearchEngine(SearchEngine):
    """Bottom-up enumeration: build the pool of well-typed terms round by round, deduped by behaviour."""

    constant_sources: tuple[ConstantSource, ...]
    function_hole_fill_mode: FunctionHoleFillMode
    polymorphism_instantiation: PolymorphismInstantiation
    budget: Budget

    def run(
        self,
        *,
        task: Task,
        library: Library,
        constraints: tuple[Constraint, ...],
        cost: Cost,
    ) -> SearchResult:
        train = [(ex.input, ex.output) for ex in task.train if ex.output is not None]
        contexts = tuple(Context(grid) for grid, _ in train)
        target: Signature = tuple(output for _, output in train)
        state = _RunState(task=task, library=library, cost=cost)

        pool = self._enumerate(Scope(()), contexts, self.budget, state)
        # ARC task outputs are grids; a general driver would derive the goal type from the task.
        solutions = extract(pool, GRID, target, constraints, task, library)

        return SearchResult(
            ranked_programs=solutions,
            stats=SearchStats(
                engine=type(self).__name__,
                considered=state.tally.considered,
                accepted=len(solutions),
                extra=state.tally.as_extra(),
            ),
        )

    def _enumerate(
        self,
        scope: Scope,
        contexts: tuple[Context, ...],
        budget: Budget,
        state: _RunState,
    ) -> Pool:
        """Build the full typed pool for ``(scope, contexts)`` up to ``budget`` (§5)."""
        pool = Pool()
        frontier: list[tuple[Program, Type]] = list(
            seed_leaves(scope, contexts, self.constant_sources)
        )
        for depth in range(budget.max_depth):
            if depth > 0:
                candidates = list(pool.typed_programs())
                frontier = [
                    application
                    for primitive in state.library.primitives
                    if not primitive.is_variadic  # variadic composition is a later layer (§5.2)
                    for application in first_order_applications(primitive, candidates, state.counter)
                ]
            self._absorb(frontier, contexts, pool, state)
            pool = self._select_frontier(pool, budget)
        return pool

    def _absorb(
        self,
        candidates: list[tuple[Program, Type]],
        contexts: tuple[Context, ...],
        pool: Pool,
        state: _RunState,
    ) -> None:
        """Evaluate, prune (intrinsic-local only, §5.6), and dedup each candidate into ``pool``."""
        for program, vtype in candidates:
            state.tally.considered += 1
            signature = compute_signature(program, contexts, state.library)
            if signature is None:  # fully undefined — errors on every context
                state.tally.errored += 1
                continue
            if not signature_matches_type(signature, vtype):  # runtime type mismatch
                state.tally.pruned += 1
                continue
            cost = state.cost.of(program, state.task, state.library)
            if not pool.add_dedup(vtype, signature, program, cost):
                state.tally.deduped += 1

    def _select_frontier(self, pool: Pool, budget: Budget) -> Pool:
        """Keep the cheapest ``budget.max_pool`` entries to carry into the next round (§5.7)."""
        return pool.cheapest(budget.max_pool)


@dataclass(frozen=True, slots=True, kw_only=True)
class BeamBottomUpSearchEngine(BottomUpSearchEngine):
    """Bottom-up enumeration with a fixed beam: keep only the cheapest ``beam_width`` per round."""

    beam_width: int

    def _select_frontier(self, pool: Pool, budget: Budget) -> Pool:
        return pool.cheapest(self.beam_width)
