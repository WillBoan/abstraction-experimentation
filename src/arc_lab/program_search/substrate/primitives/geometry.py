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
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.types import GRID


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


def _create_unary_grid_primitive(name: str, fn: Callable[[Grid], Grid]) -> Primitive:
    """Wrap a unary grid transform as a primitive."""

    return Primitive(
        name=name,
        param_types=(GRID,),
        return_type=GRID,
        impl=fn,
    )


# Order matches simplicity/preference: earlier primitives win ties in search.
D4_LIBRARY = Library(
    name="d4",
    primitives=(
        _create_unary_grid_primitive("identity", _identity),
        _create_unary_grid_primitive("rot90", _rot90),
        _create_unary_grid_primitive("rot180", _rot180),
        _create_unary_grid_primitive("rot270", _rot270),
        _create_unary_grid_primitive("flip_h", _flip_h),
        _create_unary_grid_primitive("flip_v", _flip_v),
        _create_unary_grid_primitive("transpose", _transpose),
        _create_unary_grid_primitive("anti_transpose", _anti_transpose),
    ),
)
