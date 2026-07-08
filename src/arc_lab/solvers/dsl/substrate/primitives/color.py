"""Color primitives: atomic operations on cell colors.

``map_color`` is deliberately minimal — recolor exactly one color. Arbitrary
recolorings are then *composed* from several ``map_color`` applications, which is
the point: it is a case where searching compositions (depth > 1) finds programs
that no single primitive expresses. It takes two ``COLOR`` constants, so it also
exercises typed constant arguments.
"""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.solvers.dsl.substrate.library import Primitive
from arc_lab.solvers.dsl.substrate.types import COLOR, GRID


def _map_color(grid: Grid, source: int, target: int) -> Grid:
    """Replace every cell of color ``source`` with ``target``."""
    arr = grid.array
    arr[arr == source] = target
    return Grid(arr)


MAP_COLOR = Primitive(
    name="map_color",
    param_types=(GRID, COLOR, COLOR),
    return_type=GRID,
    impl=_map_color,
)
