"""The canonical data model for program search."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, TypeAlias

from arc_lab.core.task import Task

from ..substrate.library import Library
from ..substrate.program import Program
from ..substrate.types import Type
from .constraints import Constraint
from .cost import Cost
from .pool import Pool
from .search_result import SearchResult, SearchStats
from .signature import Signature

FunctionHoleFillMode: TypeAlias = Literal["none", "point-free", "lambda-synthesis"]
PolymorphismInstantiation: TypeAlias = Literal["monomorphize", "bounded", "unrestricted"]
ConstantSource: TypeAlias = Literal[
    "finite-enumerate",
    "harvest-from-instance",
    "functionally-derive",
    "parameterize",
]


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchEngine(ABC):
    """The search engine machinery that will be used to perform the search."""

    @abstractmethod
    def run(
        self,
        task: Task,
        library: Library,
        constraints: tuple[Constraint, ...],
        cost: Cost,
    ) -> SearchResult:
        """Find candidate programs for a task."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BottomUpSearchEngine(SearchEngine):
    """A search engine that builds programs from the bottom up."""

    # Capability flags:
    function_hole_fill_mode: FunctionHoleFillMode
    polymorphism_instantiation: PolymorphismInstantiation
    constant_sources: tuple[ConstantSource, ...]

    # Search control params:
    max_depth: int
    max_pool: int

    def run(
        self,
        *,
        task: Task,
        library: Library,
        constraints: tuple[Constraint, ...],
        cost: Cost,
    ) -> SearchResult:
        """
        Run a bottom-up search engine to generate candidate programs for a task.
        """
        pool = Pool()
        considered = errored = pruned = deduped = 0

        for _ in range(self.max_depth):
            # Compose new candidate programs from the current pool and the library
            candidate_programs: list[tuple[Program, Type]] = self._compose_candidate_programs(
                pool, library, task
            )

            for cand, cand_type in candidate_programs:
                considered += 1

                cand_sig = self._signature(cand, task, library)
                if cand_sig is None:
                    errored += 1
                    continue

                if self._prunes(cand, cand_sig, constraints):
                    pruned += 1
                    continue

                cand_cost_value = cost.evaluate(cand, task, library)

                # Add to the pool (deduplication by observational equivalence, keep cheapest by cost)
                if (
                    pool.add_dedup(
                        vtype=cand_type,
                        signature=cand_sig,
                        program=cand,
                        cost_value=cand_cost_value,
                    )
                    is False
                ):
                    deduped += 1

            pool = self._select_frontier(pool, cost)

        ranked_programs = pool.ranked(cost)

        return SearchResult(
            ranked_programs=ranked_programs,
            stats=SearchStats(
                engine=self.__class__.__name__,
                considered=considered,
                accepted=len(ranked_programs),
                extra={
                    "errored": errored,
                    "pruned": pruned,
                    "deduped": deduped,
                },
            ),
        )

    def _compose_candidate_programs(
        self,
        pool: Pool,
        library: Library,
        task: Task,
    ) -> list[tuple[Program, Type]]:
        """
        Compose new candidate programs from the current pool and the library.

        Each candidate carries the (instantiated) result type derived during
        composition.
        """
        raise NotImplementedError()

    def _signature(self, program: Program, task: Task, library: Library) -> Signature | None:
        """
        Compute the signature of a program: its output value on each training input.

        Returns ``None`` if the program raises on any input (e.g. an out-of-bounds
        ``read``) — such candidates are rejected rather than pooled.
        """
        try:
            return tuple(program.evaluate(example.input, library) for example in task.train)
        except Exception:
            return None

    def _select_frontier(self, pool: Pool, cost: Cost) -> Pool:
        """
        BottomUp: keep the cheapest max_pool
        """
        return pool.cheapest(self.max_pool)


@dataclass(frozen=True, slots=True, kw_only=True)
class BeamBottomUpSearchEngine(BottomUpSearchEngine):
    """Bottom-up search + beam search"""

    beam_width: int

    def _select_frontier(self, pool: Pool, cost: Cost) -> Pool:
        """
        BeamBottomUp: keep the cheapest beam_width
        """
        return pool.cheapest(self.beam_width)
