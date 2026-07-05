"""Combinators: primitives that glue several grid outputs into one.

These are the answer to "more expressive without new vocabulary": they compose the
*outputs* of the D4 transforms rather than the transforms themselves, so they
escape the group-closure of D4. Both are total (they never raise) — an
ill-configured combinator just produces a grid that fails the consistency check
and is discarded by search.

* :data:`OVERLAY` — cellwise merge of transformed copies, taking the non-mask
  consensus. Reconstructs a symmetric grid whose masked region is occluded.
* :data:`TILE` — arrange transformed copies into a larger mosaic.
"""

from __future__ import annotations

import numpy as np

from arc_lab.core.grid import Grid
from arc_lab.solvers.dsl.substrate.library import Primitive
from arc_lab.solvers.dsl.substrate.types import ValueType


def _overlay(mask: int, *grids: Grid) -> Grid:
    """Merge ``grids`` cell-by-cell, taking the single non-``mask`` value present."""
    base = grids[0].array
    if any(g.shape != grids[0].shape for g in grids):
        return grids[0]  # incompatible copies (e.g. a non-shape-preserving transform)
    stack = np.stack([g.array for g in grids])  # (k, H, W)
    masked = stack == mask
    # Highest non-mask value at each cell (-1 where every copy is masked). Where the
    # copies agree this is the true color; where they conflict it is an arbitrary but
    # deterministic value, so the result simply fails the consistency check.
    high = np.where(masked, -1, stack).max(axis=0)
    determined = high >= 0
    out = base.copy()
    out[determined] = high[determined]
    return Grid(out)


def _tile(rows: int, cols: int, *cells: Grid) -> Grid:
    """Lay ``cells`` (row-major) into a ``rows`` x ``cols`` mosaic of equal blocks."""
    if len(cells) != rows * cols:
        return cells[0]
    bh, bw = cells[0].shape
    if any(c.shape != (bh, bw) for c in cells):
        return cells[0]  # non-uniform blocks (e.g. a rotation of a non-square grid)
    out = np.zeros((rows * bh, cols * bw), dtype=np.int8)
    for index, cell in enumerate(cells):
        r, c = divmod(index, cols)
        out[r * bh : (r + 1) * bh, c * bw : (c + 1) * bw] = cell.array
    return Grid(out)


OVERLAY = Primitive(
    name="overlay",
    param_types=(ValueType.COLOR,),
    return_type=ValueType.GRID,
    impl=_overlay,
    variadic_param=ValueType.GRID,
)

TILE = Primitive(
    name="tile",
    param_types=(ValueType.INT, ValueType.INT),
    return_type=ValueType.GRID,
    impl=_tile,
    variadic_param=ValueType.GRID,
)

COMBINATORS: tuple[Primitive, ...] = (OVERLAY, TILE)
