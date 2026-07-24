"""Grid perceivers (ONTOLOGY.md L2): read scalar/summary facts off a grid.

Perceivers are what turn literal constants into *derived* values — "recolor the background"
(``map_color(g, most_common_color(g), c)``) instead of "recolor color 3". All are deterministic:
color-frequency ties break to the **lowest color value**, and ``palette`` returns ascending order.

``background_color`` is deliberately *not* a separate primitive: today it would be behaviorally
identical to ``most_common_color`` (the standard ARC background heuristic), and a duplicate is pure
search cost — observational equivalence would collapse them in-pool anyway. It becomes its own
primitive if and when a smarter heuristic distinguishes them.
"""

from __future__ import annotations

import numpy as np

from arc_lab.core.geometry import Offset
from arc_lab.core.grid import Grid
from arc_lab.program_search.substrate.library import Primitive, Value
from arc_lab.program_search.substrate.types import COLOR, GRID, INT, OFFSET, list_type, pair_type


def _color_counts(grid: Grid) -> np.ndarray:
    return np.bincount(grid.array.ravel(), minlength=10)


def _most_common_color(grid: Grid) -> int:
    return int(np.argmax(_color_counts(grid)))  # argmax takes the first (lowest) on ties


def _least_common_color(grid: Grid) -> int:
    counts = _color_counts(grid)
    present = np.flatnonzero(counts)
    return int(present[np.argmin(counts[present])])  # lowest color on ties, colors absent excluded


def _count_color(grid: Grid, color: int) -> int:
    return int(np.count_nonzero(grid.array == color))


def _num_colors(grid: Grid) -> int:
    return int(np.count_nonzero(_color_counts(grid)))


def _palette(grid: Grid) -> Value:
    return tuple(int(c) for c in np.flatnonzero(_color_counts(grid)))  # ascending by construction


def _shape(grid: Grid) -> Value:
    return (grid.height, grid.width)


def _extent(grid: Grid) -> Offset:
    """The grid's size as an :class:`Offset` -- the addressing-typed companion to ``shape``.

    Kept ALONGSIDE ``shape`` rather than replacing it: ``shape``'s ``pair[int, int]`` is the right
    answer when the caller wants two independent ints, and ``extent`` is the right one when the
    result feeds the addressing algebra (``rect``, ``offset_scale``, ``blank``). Replacing it would
    move a return type for no gain.
    """
    return Offset(grid.height, grid.width)


MOST_COMMON_COLOR = Primitive(
    name="most_common_color", param_types=(GRID,), return_type=COLOR, impl=_most_common_color
)
LEAST_COMMON_COLOR = Primitive(
    name="least_common_color", param_types=(GRID,), return_type=COLOR, impl=_least_common_color
)
COUNT_COLOR = Primitive(
    name="count_color", param_types=(GRID, COLOR), return_type=INT, impl=_count_color
)
NUM_COLORS = Primitive(name="num_colors", param_types=(GRID,), return_type=INT, impl=_num_colors)
PALETTE = Primitive(
    name="palette", param_types=(GRID,), return_type=list_type(COLOR), impl=_palette
)
SHAPE = Primitive(name="shape", param_types=(GRID,), return_type=pair_type(INT, INT), impl=_shape)
EXTENT = Primitive(name="extent", param_types=(GRID,), return_type=OFFSET, impl=_extent)

PERCEIVE_PRIMITIVES = (
    MOST_COMMON_COLOR,
    LEAST_COMMON_COLOR,
    COUNT_COLOR,
    NUM_COLORS,
    PALETTE,
    SHAPE,
    EXTENT,
)
