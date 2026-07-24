"""The addressing algebra: build, read, and do arithmetic on :class:`Coord` / :class:`Offset` /
:class:`Rect` (``core/geometry.py``).

These are pure integer geometry -- no grid is touched here. That separation is the point: where
``mask.py`` answers *which cells*, this answers *where* and *what area*, at O(1) and without being
pinned inside a grid's bounds. ``regions.py`` is where the two meet.

**The affine discipline.** ``coord_add`` takes a position and a *displacement*; ``coord_sub`` of two
positions yields a displacement. There is deliberately **no** ``coord + coord`` -- adding two
positions is meaningless, and leaving it out makes that a type error the enumerator can never build,
rather than a plausible-looking term it wastes budget on.

``offset_scale`` is the tile-lattice step: "``k`` whole tiles over" is ``offset_scale(extent, k)``,
which is the shape cfb2ce5a's grid-of-tiles is actually made of.
"""

from __future__ import annotations

from arc_lab.core.geometry import Coord, Offset, Rect
from arc_lab.program_search.substrate.library import Primitive
from arc_lab.program_search.substrate.types import COORD, INT, OFFSET, RECT

# -- constructors and accessors --------------------------------------------------------------------


def _coord(row: int, col: int) -> Coord:
    return Coord(row, col)


def _coord_row(coord: Coord) -> int:
    return coord.row


def _coord_col(coord: Coord) -> int:
    return coord.col


def _offset(d_row: int, d_col: int) -> Offset:
    return Offset(d_row, d_col)


def _offset_row(offset: Offset) -> int:
    return offset.d_row


def _offset_col(offset: Offset) -> int:
    return offset.d_col


def _rect(origin: Coord, extent: Offset) -> Rect:
    return Rect(origin, extent)  # a degenerate extent raises and prunes as bottom


def _rect_origin(rect: Rect) -> Coord:
    return rect.origin


def _rect_extent(rect: Rect) -> Offset:
    return rect.extent


def _rect_area(rect: Rect) -> int:
    return rect.area


# -- affine arithmetic -----------------------------------------------------------------------------


def _coord_add(coord: Coord, offset: Offset) -> Coord:
    return Coord(coord.row + offset.d_row, coord.col + offset.d_col)


def _coord_sub(to: Coord, origin: Coord) -> Offset:
    """The displacement from ``origin`` to ``to`` -- position minus position IS a displacement."""
    return Offset(to.row - origin.row, to.col - origin.col)


def _offset_add(a: Offset, b: Offset) -> Offset:
    return Offset(a.d_row + b.d_row, a.d_col + b.d_col)


def _offset_scale(offset: Offset, factor: int) -> Offset:
    return Offset(offset.d_row * factor, offset.d_col * factor)


def _offset_neg(offset: Offset) -> Offset:
    return Offset(-offset.d_row, -offset.d_col)


def _rect_translate(rect: Rect, offset: Offset) -> Rect:
    return Rect(_coord_add(rect.origin, offset), rect.extent)


# -- frames ----------------------------------------------------------------------------------------


def _to_local(frame: Rect, coord: Coord) -> Coord:
    """Re-express a global position in ``frame``'s coordinates (the origin becomes ``(0, 0)``)."""
    return Coord(coord.row - frame.origin.row, coord.col - frame.origin.col)


def _to_global(frame: Rect, coord: Coord) -> Coord:
    """The inverse of :func:`_to_local` -- a frame-local position back in grid coordinates."""
    return Coord(coord.row + frame.origin.row, coord.col + frame.origin.col)


COORD_OF = Primitive(name="coord", param_types=(INT, INT), return_type=COORD, impl=_coord)
COORD_ROW = Primitive(name="coord_row", param_types=(COORD,), return_type=INT, impl=_coord_row)
COORD_COL = Primitive(name="coord_col", param_types=(COORD,), return_type=INT, impl=_coord_col)
OFFSET_OF = Primitive(name="offset", param_types=(INT, INT), return_type=OFFSET, impl=_offset)
OFFSET_ROW = Primitive(name="offset_row", param_types=(OFFSET,), return_type=INT, impl=_offset_row)
OFFSET_COL = Primitive(name="offset_col", param_types=(OFFSET,), return_type=INT, impl=_offset_col)
RECT_OF = Primitive(name="rect", param_types=(COORD, OFFSET), return_type=RECT, impl=_rect)
RECT_ORIGIN = Primitive(
    name="rect_origin", param_types=(RECT,), return_type=COORD, impl=_rect_origin
)
RECT_EXTENT = Primitive(
    name="rect_extent", param_types=(RECT,), return_type=OFFSET, impl=_rect_extent
)
RECT_AREA = Primitive(name="rect_area", param_types=(RECT,), return_type=INT, impl=_rect_area)
COORD_ADD = Primitive(
    name="coord_add", param_types=(COORD, OFFSET), return_type=COORD, impl=_coord_add
)
COORD_SUB = Primitive(
    name="coord_sub", param_types=(COORD, COORD), return_type=OFFSET, impl=_coord_sub
)
OFFSET_ADD = Primitive(
    name="offset_add", param_types=(OFFSET, OFFSET), return_type=OFFSET, impl=_offset_add
)
OFFSET_SCALE = Primitive(
    name="offset_scale", param_types=(OFFSET, INT), return_type=OFFSET, impl=_offset_scale
)
OFFSET_NEG = Primitive(
    name="offset_neg", param_types=(OFFSET,), return_type=OFFSET, impl=_offset_neg
)
RECT_TRANSLATE = Primitive(
    name="rect_translate", param_types=(RECT, OFFSET), return_type=RECT, impl=_rect_translate
)
TO_LOCAL = Primitive(name="to_local", param_types=(RECT, COORD), return_type=COORD, impl=_to_local)
TO_GLOBAL = Primitive(
    name="to_global", param_types=(RECT, COORD), return_type=COORD, impl=_to_global
)

ADDRESSING_PRIMITIVES = (
    COORD_OF,
    COORD_ROW,
    COORD_COL,
    OFFSET_OF,
    OFFSET_ROW,
    OFFSET_COL,
    RECT_OF,
    RECT_ORIGIN,
    RECT_EXTENT,
    RECT_AREA,
    COORD_ADD,
    COORD_SUB,
    OFFSET_ADD,
    OFFSET_SCALE,
    OFFSET_NEG,
    RECT_TRANSLATE,
    TO_LOCAL,
    TO_GLOBAL,
)
