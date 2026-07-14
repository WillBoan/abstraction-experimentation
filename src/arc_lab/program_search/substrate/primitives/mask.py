"""The L3 region family (ONTOLOGY.md): ``Mask`` intros, set-algebra, and elims.

The bridge from "grid" to "object": a :class:`~arc_lab.core.mask.Mask` selects cells to crop to,
paint through, or combine set-wise. "Background" throughout means the grid's most-common color (the
standard ARC heuristic, shared with ``perceive.py``). Domain errors — mismatched shapes, an empty
selection — raise and prune as ``⊥``; there is no meaningful no-op for them.
"""

from __future__ import annotations

import numpy as np

from arc_lab.core.grid import Grid
from arc_lab.core.mask import Mask
from arc_lab.program_search.substrate.library import Primitive
from arc_lab.program_search.substrate.types import COLOR, GRID, MASK


def _background(grid: Grid) -> int:
    return int(np.argmax(np.bincount(grid.array.ravel(), minlength=10)))


def _bounds(mask: Mask) -> tuple[int, int, int, int]:
    """The inclusive (row_lo, row_hi, col_lo, col_hi) bbox of the selected cells; raises if empty."""
    rows, cols = np.nonzero(mask.array)
    if rows.size == 0:
        raise ValueError("mask selects no cells")
    return int(rows.min()), int(rows.max()), int(cols.min()), int(cols.max())


def _require_same_shape(a: Mask | Grid, b: Mask | Grid, op: str) -> None:
    if a.shape != b.shape:
        raise ValueError(f"{op} requires matching shapes, got {a.shape} and {b.shape}")


# -- intros ----------------------------------------------------------------------------------------


def _mask_by_color(grid: Grid, color: int) -> Mask:
    return Mask(grid.array == color)


def _nonbg_mask(grid: Grid) -> Mask:
    return Mask(grid.array != _background(grid))


def _bbox_mask(grid: Grid) -> Mask:
    """The filled bounding-box region of the non-background content."""
    row_lo, row_hi, col_lo, col_hi = _bounds(_nonbg_mask(grid))
    out = np.zeros(grid.shape, dtype=np.bool_)
    out[row_lo : row_hi + 1, col_lo : col_hi + 1] = True  # noqa: E203, RUF100
    return Mask(out)


# -- set algebra -----------------------------------------------------------------------------------


def _mask_union(a: Mask, b: Mask) -> Mask:
    _require_same_shape(a, b, "mask_union")
    return Mask(a.array | b.array)


def _mask_intersect(a: Mask, b: Mask) -> Mask:
    _require_same_shape(a, b, "mask_intersect")
    return Mask(a.array & b.array)


def _mask_difference(a: Mask, b: Mask) -> Mask:
    _require_same_shape(a, b, "mask_difference")
    return Mask(a.array & ~b.array)


def _mask_complement(mask: Mask) -> Mask:
    return Mask(~mask.array)


# -- elims -----------------------------------------------------------------------------------------


def _crop_to_mask(grid: Grid, mask: Mask) -> Grid:
    """Crop the grid to the mask's bounding box (the whole rectangle, unselected cells included)."""
    _require_same_shape(grid, mask, "crop_to_mask")
    row_lo, row_hi, col_lo, col_hi = _bounds(mask)
    return Grid(grid.array[row_lo : row_hi + 1, col_lo : col_hi + 1])


def _paint_through_mask(grid: Grid, mask: Mask, color: int) -> Grid:
    _require_same_shape(grid, mask, "paint_through_mask")
    arr = grid.array
    arr[mask.array] = color
    return Grid(arr)


def _crop_to_content(grid: Grid) -> Grid:
    """Crop to the bbox of all non-background cells; a uniform grid raises (no content)."""
    return _crop_to_mask(grid, _nonbg_mask(grid))


MASK_BY_COLOR = Primitive(
    name="mask_by_color", param_types=(GRID, COLOR), return_type=MASK, impl=_mask_by_color
)
NONBG_MASK = Primitive(name="nonbg_mask", param_types=(GRID,), return_type=MASK, impl=_nonbg_mask)
BBOX_MASK = Primitive(name="bbox_mask", param_types=(GRID,), return_type=MASK, impl=_bbox_mask)
MASK_UNION = Primitive(
    name="mask_union", param_types=(MASK, MASK), return_type=MASK, impl=_mask_union
)
MASK_INTERSECT = Primitive(
    name="mask_intersect", param_types=(MASK, MASK), return_type=MASK, impl=_mask_intersect
)
MASK_DIFFERENCE = Primitive(
    name="mask_difference", param_types=(MASK, MASK), return_type=MASK, impl=_mask_difference
)
MASK_COMPLEMENT = Primitive(
    name="mask_complement", param_types=(MASK,), return_type=MASK, impl=_mask_complement
)
CROP_TO_MASK = Primitive(
    name="crop_to_mask", param_types=(GRID, MASK), return_type=GRID, impl=_crop_to_mask
)
PAINT_THROUGH_MASK = Primitive(
    name="paint_through_mask",
    param_types=(GRID, MASK, COLOR),
    return_type=GRID,
    impl=_paint_through_mask,
)
CROP_TO_CONTENT = Primitive(
    name="crop_to_content", param_types=(GRID,), return_type=GRID, impl=_crop_to_content
)

MASK_PRIMITIVES = (
    MASK_BY_COLOR,
    NONBG_MASK,
    BBOX_MASK,
    MASK_UNION,
    MASK_INTERSECT,
    MASK_DIFFERENCE,
    MASK_COMPLEMENT,
    CROP_TO_MASK,
    PAINT_THROUGH_MASK,
    CROP_TO_CONTENT,
)
