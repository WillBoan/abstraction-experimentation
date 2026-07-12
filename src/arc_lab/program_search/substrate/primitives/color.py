"""Color primitives: atomic operations on cell colors.

``map_color`` is deliberately minimal — recolor exactly one color. Arbitrary
recolorings are then *composed* from several ``map_color`` applications, which is
the point: it is a case where searching compositions (depth > 1) finds programs
that no single primitive expresses. It takes two ``COLOR`` constants, so it also
exercises typed constant arguments.

``swap_colors`` exists because a *swap* is exactly what ``map_color`` provably cannot
express at depth 2 (the second application clobbers the first's result — a measured
finding, see ONTOLOGY.md). ``filter_color`` keeps one color and floods everything
else to the grid's most-common color (the standard background heuristic).
"""

from __future__ import annotations

import numpy as np

from arc_lab.core.grid import Grid
from arc_lab.program_search.substrate.library import Primitive
from arc_lab.program_search.substrate.types import COLOR, GRID


def _map_color(grid: Grid, source: int, target: int) -> Grid:
    """Replace every cell of color ``source`` with ``target``."""
    arr = grid.array
    arr[arr == source] = target
    return Grid(arr)


def _swap_colors(grid: Grid, first: int, second: int) -> Grid:
    """Exchange colors ``first`` and ``second`` throughout the grid."""
    arr = grid.array
    first_cells = arr == first
    arr[arr == second] = first
    arr[first_cells] = second
    return Grid(arr)


def _filter_color(grid: Grid, keep: int) -> Grid:
    """Keep cells of color ``keep``; flood everything else to the most-common color."""
    arr = grid.array
    background = int(np.argmax(np.bincount(arr.ravel(), minlength=10)))
    arr[arr != keep] = background
    return Grid(arr)


MAP_COLOR = Primitive(
    name="map_color",
    param_types=(GRID, COLOR, COLOR),
    return_type=GRID,
    impl=_map_color,
)
SWAP_COLORS = Primitive(
    name="swap_colors",
    param_types=(GRID, COLOR, COLOR),
    return_type=GRID,
    impl=_swap_colors,
)
FILTER_COLOR = Primitive(
    name="filter_color",
    param_types=(GRID, COLOR),
    return_type=GRID,
    impl=_filter_color,
)
