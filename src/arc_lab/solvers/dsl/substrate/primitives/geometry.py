"""The geometric primitive library: the dihedral group D4.

These eight whole-grid transforms are the symmetries of a square — four rotations
and four reflections. They form a group *closed under composition* (any chain of
them is itself one of the eight), which is exactly why searching over their
compositions gains nothing and why expressiveness must instead come from richer
combinators over their outputs. See the module for the seed solver that searches
this library by single application.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from arc_lab.core.grid import Grid
from arc_lab.solvers.dsl.substrate.library import Library, Primitive
from arc_lab.solvers.dsl.substrate.types import ValueType


def _identity(g: Grid) -> Grid:
    return g


def _rot90(g: Grid) -> Grid:
    return Grid(np.rot90(g.array, 1))


def _rot180(g: Grid) -> Grid:
    return Grid(np.rot90(g.array, 2))


def _rot270(g: Grid) -> Grid:
    return Grid(np.rot90(g.array, 3))


def _flip_h(g: Grid) -> Grid:
    return Grid(np.fliplr(g.array))


def _flip_v(g: Grid) -> Grid:
    return Grid(np.flipud(g.array))


def _transpose(g: Grid) -> Grid:
    return Grid(g.array.T)


def _anti_transpose(g: Grid) -> Grid:
    return Grid(np.rot90(g.array, 2).T)


def _unary(name: str, fn: Callable[[Grid], Grid]) -> Primitive:
    return Primitive(
        name=name,
        param_types=(ValueType.GRID,),
        return_type=ValueType.GRID,
        impl=fn,
    )


# Order matches simplicity/preference: earlier primitives win ties in search.
D4_LIBRARY = Library(
    name="d4",
    primitives=(
        _unary("identity", _identity),
        _unary("rot90", _rot90),
        _unary("rot180", _rot180),
        _unary("rot270", _rot270),
        _unary("flip_h", _flip_h),
        _unary("flip_v", _flip_v),
        _unary("transpose", _transpose),
        _unary("anti_transpose", _anti_transpose),
    ),
)
