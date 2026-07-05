"""Search strategies over programs.

A :class:`~arc_lab.solvers.dsl.search.base.Search` turns a task and a library into
ranked candidate programs. It is deliberately independent of *which* primitives it
searches, so the same strategy works over any library, and a solver can swap or
compose strategies (single application, combinator search, learned-prior guidance,
LLM-proposed programs, ...) without touching the vocabulary.
"""

from arc_lab.solvers.dsl.search.base import Search
from arc_lab.solvers.dsl.search.composite import CompositeSearch
from arc_lab.solvers.dsl.search.enumerate import Enumerate
from arc_lab.solvers.dsl.search.overlay import OverlaySearch
from arc_lab.solvers.dsl.search.single_apply import SingleApply
from arc_lab.solvers.dsl.search.tile import TileSearch

__all__ = [
    "CompositeSearch",
    "Enumerate",
    "OverlaySearch",
    "Search",
    "SingleApply",
    "TileSearch",
]
