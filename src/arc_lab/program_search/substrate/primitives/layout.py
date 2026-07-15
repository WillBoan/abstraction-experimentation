"""L2 layout primitives (ONTOLOGY.md): construct, move, join, and resize whole grids.

Size conventions follow ``scaling.py``: a result that would exceed the ARC ``<=30``-per-side cap is
a **no-op returning the input grid** (search discards it via consistency) for the transforms that
have an input grid to return (``pad``/``tile_repeat``); ``blank`` has no input to fall back to, so
out-of-range dimensions raise. ``translate`` fills vacated cells with color 0 (documented choice —
a background-filling variant is minting material for the learning loop, not a second primitive).
``downsample`` is stride sampling (``arr[::k, ::k]``): the cheap inverse-of-scale, not a
block-consensus shrink.
"""

from __future__ import annotations

import numpy as np

from arc_lab.core.grid import Grid
from arc_lab.program_search.substrate.library import Primitive
from arc_lab.program_search.substrate.types import COLOR, GRID, INT

_MAX_SIDE = 30


def _blank(height: int, width: int, color: int) -> Grid:
    if not (1 <= height <= _MAX_SIDE and 1 <= width <= _MAX_SIDE):
        raise ValueError(f"blank dimensions must be in [1, {_MAX_SIDE}], got {(height, width)}")
    return Grid(np.full((height, width), color))


def _translate(grid: Grid, d_row: int, d_col: int) -> Grid:
    """Shift all cells by (d_row, d_col); vacated cells fill with color 0."""
    out = np.zeros(grid.shape, dtype=np.int8)
    height, width = grid.shape
    src = grid.array
    row_lo, row_hi = max(0, d_row), min(height, height + d_row)
    col_lo, col_hi = max(0, d_col), min(width, width + d_col)
    if row_lo < row_hi and col_lo < col_hi:
        out[row_lo:row_hi, col_lo:col_hi] = src[
            row_lo - d_row : row_hi - d_row,  # noqa: E203, RUF100
            col_lo - d_col : col_hi - d_col,  # noqa: E203, RUF100
        ]
    return Grid(out)


def _concat_h(left: Grid, right: Grid) -> Grid:
    if left.height != right.height:
        raise ValueError(f"concat_h requires equal heights, got {left.height} and {right.height}")
    if left.width + right.width > _MAX_SIDE:
        return left  # over the ARC size cap: no-op, discarded via consistency
    return Grid(np.hstack((left.array, right.array)))


def _concat_v(top: Grid, bottom: Grid) -> Grid:
    if top.width != bottom.width:
        raise ValueError(f"concat_v requires equal widths, got {top.width} and {bottom.width}")
    if top.height + bottom.height > _MAX_SIDE:
        return top  # over the ARC size cap: no-op, discarded via consistency
    return Grid(np.vstack((top.array, bottom.array)))


def _pad(grid: Grid, thickness: int, color: int) -> Grid:
    if thickness < 1 or max(grid.shape) + 2 * thickness > _MAX_SIDE:
        return grid  # out of range: no-op, discarded via consistency (scaling.py convention)
    return Grid(np.pad(grid.array, thickness, constant_values=color))


def _tile_repeat(grid: Grid, rows: int, cols: int) -> Grid:
    if rows < 1 or cols < 1 or grid.height * rows > _MAX_SIDE or grid.width * cols > _MAX_SIDE:
        return grid  # out of range: no-op, discarded via consistency (scaling.py convention)
    return Grid(np.tile(grid.array, (rows, cols)))


def _downsample(grid: Grid, factor: int) -> Grid:
    """Every ``factor``-th cell (stride sampling) — the cheap inverse of ``scale``."""
    if factor < 1:
        raise ValueError(f"downsample factor must be >= 1, got {factor}")
    return Grid(grid.array[::factor, ::factor])


BLANK = Primitive(name="blank", param_types=(INT, INT, COLOR), return_type=GRID, impl=_blank)
TRANSLATE = Primitive(
    name="translate", param_types=(GRID, INT, INT), return_type=GRID, impl=_translate
)
CONCAT_H = Primitive(name="concat_h", param_types=(GRID, GRID), return_type=GRID, impl=_concat_h)
CONCAT_V = Primitive(name="concat_v", param_types=(GRID, GRID), return_type=GRID, impl=_concat_v)
PAD = Primitive(name="pad", param_types=(GRID, INT, COLOR), return_type=GRID, impl=_pad)
TILE_REPEAT = Primitive(
    name="tile_repeat", param_types=(GRID, INT, INT), return_type=GRID, impl=_tile_repeat
)
DOWNSAMPLE = Primitive(
    name="downsample", param_types=(GRID, INT), return_type=GRID, impl=_downsample
)

LAYOUT_PRIMITIVES = (BLANK, TRANSLATE, CONCAT_H, CONCAT_V, PAD, TILE_REPEAT, DOWNSAMPLE)
