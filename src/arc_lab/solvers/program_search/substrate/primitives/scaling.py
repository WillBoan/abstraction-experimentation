"""Scaling primitives.

``scale`` upsamples a grid by an integer factor (each cell becomes a k x k block).
It takes an ``INT`` constant and composes with geometry (e.g. ``scale(rot180(x), k)``),
another case where composition matters. The output is capped at the largest ARC
grid side (30) so ill-chosen factors produce a no-op rather than a huge array.
"""

from __future__ import annotations

import numpy as np

from arc_lab.core.grid import Grid
from arc_lab.solvers.program_search.substrate.library import Primitive
from arc_lab.solvers.program_search.substrate.types import GRID, INT

_MAX_SIDE = 30


def _scale(grid: Grid, factor: int) -> Grid:
    """Upsample ``grid`` by an integer ``factor`` (nearest-neighbour block expand)."""
    if factor < 1 or factor * max(grid.shape) > _MAX_SIDE:
        return grid  # out of range -> no-op (which search likely discards via consistency)
    block = np.ones((factor, factor), dtype=np.int8)
    return Grid(np.kron(grid.array, block))


SCALE = Primitive(
    name="scale",
    param_types=(GRID, INT),
    return_type=GRID,
    impl=_scale,
)
