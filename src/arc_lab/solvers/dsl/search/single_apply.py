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
from arc_lab.solvers.dsl.search.base import Search
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.program import (
    Apply,
    Input,
    Program,
    format_program,
    is_consistent,
)

logger = logging.getLogger(__name__)


class SingleApply(Search):
    """Search programs of the form ``primitive(Input)`` for one primitive."""

    def find(self, task: Task, library: Library) -> list[Program]:
        programs: list[Program] = []
        for prim in library.unary_grid_primitives():
            program: Program = Apply(prim.name, (Input(),))
            if is_consistent(program, task, library):
                logger.debug("SingleApply accept %s", format_program(program))
                programs.append(program)
        return programs
