from __future__ import annotations

import logging

from arc_lab.core.task import Task

from ..substrate.library import Library
from ..substrate.program import Apply, Input, Program
from .search_strategy import SearchResult, SearchStats, SearchStrategy

logger = logging.getLogger(__name__)


class SingleApplySearch(SearchStrategy):
    """
    A single-apply search strategy applies each program in the library to the task's inputs
    exactly once, returning the first program that produces a correct output for all training
    pairs.

    An extremely basic search strategy.
    """

    def find(self, task: Task, library: Library) -> SearchResult:
        # For SingleApplySearch, the candidate programs are all of the unary `GRID -> GRID` primitives.
        candidate_programs: list[Program] = [
            Apply(prim.name, (Input(),)) for prim in library.unary_grid_primitives()
        ]

        accepted_programs: list[Program] = []
        considered = 0

        for program in candidate_programs:
            considered += 1
            if self.all_constraints_hold(program, task, library):
                logger.debug("SingleApplySearch accept %s", program)
                accepted_programs.append(program)

        stats = SearchStats(
            strategy=self.__class__.__name__,
            considered=considered,
            accepted=len(accepted_programs),
        )
        logger.info(stats.summary())
        return SearchResult(accepted_programs=tuple(accepted_programs), stats=stats)
