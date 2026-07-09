"""The simplest search: apply one primitive to the input.

For each unary ``GRID -> GRID`` primitive in the library, form the program
``primitive(Input)`` and keep it if it reproduces every training output.

This is the whole search space of the seed geometric solver; richer strategies
(bounded composition, combinator search, learned guidance) subclass :class:`Search`
alongside it.
"""

from __future__ import annotations

import logging

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search.base import Search, SearchResult, SearchStats
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.program import Apply, Input, Program

logger = logging.getLogger(__name__)


class SingleApply(Search):
    """Search programs of the form ``primitive(Input)`` for one primitive."""

    def find(self, task: Task, library: Library) -> SearchResult:
        programs: list[Program] = []
        considered = 0
        for prim in library.unary_grid_primitives():
            considered += 1
            program: Program = Apply(prim.name, (Input(),))
            if self.accepts(program, task, library):
                logger.debug("SingleApply accept %s", program)
                programs.append(program)
        stats = SearchStats(strategy="SingleApply", considered=considered, returned=len(programs))
        logger.info(stats.summary())
        return SearchResult(programs=tuple(programs), stats=stats)
