"""Compose several search strategies into one.

Runs each strategy in turn and concatenates their candidate programs (deduplicated,
order preserved). This is how a solver offers "try single transforms, else try the
overlay combinator, else try tiling" without any strategy knowing about the others.
"""

from __future__ import annotations

from collections.abc import Sequence

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search.base import Search
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.program import Program


class CompositeSearch(Search):
    """Concatenate the results of several search strategies."""

    def __init__(self, strategies: Sequence[Search]) -> None:
        self.strategies = tuple(strategies)

    def find(self, task: Task, library: Library) -> list[Program]:
        seen: set[Program] = set()
        combined: list[Program] = []
        for strategy in self.strategies:
            for program in strategy.find(task, library):
                if program not in seen:
                    seen.add(program)
                    combined.append(program)
        return combined
