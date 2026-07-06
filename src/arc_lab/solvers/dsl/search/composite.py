"""Compose several search strategies into one.

Runs each strategy in turn and concatenates their candidate programs (deduplicated,
order preserved). This is how a solver offers "try single transforms, else try the
overlay combinator, else try tiling" without any strategy knowing about the others.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search.base import Search, SearchResult, SearchStats
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.program import Program

logger = logging.getLogger(__name__)


class CompositeSearch(Search):
    """Concatenate the results of several search strategies."""

    def __init__(self, strategies: Sequence[Search]) -> None:
        # Constraints live on the wrapped strategies; the composite only concatenates.
        super().__init__()
        self.strategies = tuple(strategies)

    def find(self, task: Task, library: Library) -> SearchResult:
        # Each wrapped strategy logs its own INFO summary; here we report the
        # deduplicated total and the summed search effort across strategies.
        # (The task id is supplied by TaskIdFilter as a prefix.)
        seen: set[Program] = set()
        combined: list[Program] = []
        considered = 0
        for strategy in self.strategies:
            result = strategy.find(task, library)
            considered += result.stats.considered
            for program in result.programs:
                if program not in seen:
                    seen.add(program)
                    combined.append(program)
        stats = SearchStats(
            strategy="CompositeSearch",
            considered=considered,
            returned=len(combined),
            extra={"strategies": len(self.strategies)},
        )
        logger.info(stats.summary())
        return SearchResult(programs=tuple(combined), stats=stats)
