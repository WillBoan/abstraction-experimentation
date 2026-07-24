"""The addressing types: :class:`Coord`, :class:`Offset`, :class:`Rect`.

Where :class:`~arc_lab.core.mask.Mask` answers *which cells* (exactly, for any shape, but at
O(H x W) and only ever for one grid shape), these answer *where* and *what area* -- at O(1), with
arithmetic, and **without being pinned inside the grid's bounds**. A :class:`Rect` may hang off the
edge; that is the point, and it is what a mask structurally cannot express. Clipping is explicit
(``rect_clip``), never implied.

The split is deliberate:

* **Coord** -- an absolute position. May be negative, because a rect's origin may sit off-grid.
* **Offset** -- a *displacement*, not a position. Keeping them distinct makes ``coord + coord`` a
  type error rather than a plausible-looking bug, and makes ``offset * k`` -- the tile-lattice step
  -- say what it means.
* **Rect** -- ``origin + extent``, so "size" needs no third type.

All three are frozen dataclasses, hence **hashable by value**. That is load-bearing, not incidental:
``search/signature.py`` uses runtime values as observational-equivalence keys in the search pool, so
a type with identity semantics could not flow through a program at all.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Coord:
    """An absolute (row, col) position. Negative components are legal -- an off-grid rect origin."""

    row: int
    col: int

    def __str__(self) -> str:
        return f"({self.row}, {self.col})"


@dataclass(frozen=True, slots=True)
class Offset:
    """A (d_row, d_col) displacement -- deliberately NOT a position (see the module docstring)."""

    d_row: int
    d_col: int

    def __str__(self) -> str:
        return f"<{self.d_row}, {self.d_col}>"


@dataclass(frozen=True, slots=True)
class Rect:
    """An axis-aligned rectangle: an origin plus a strictly-positive extent.

    A degenerate extent raises rather than yielding an empty rect, matching :class:`Mask` and
    :class:`~arc_lab.core.grid.Grid` (both non-empty by construction) -- so ``rect_clip`` on a
    fully out-of-bounds rect is a domain error that prunes as bottom, not a silent empty result.
    """

    origin: Coord
    extent: Offset

    def __post_init__(self) -> None:
        if self.extent.d_row < 1 or self.extent.d_col < 1:
            raise ValueError(f"rect extent must be positive in both dimensions, got {self.extent}")

    @property
    def height(self) -> int:
        return self.extent.d_row

    @property
    def width(self) -> int:
        return self.extent.d_col

    @property
    def area(self) -> int:
        return self.extent.d_row * self.extent.d_col

    def __str__(self) -> str:
        return f"[{self.origin} {self.extent}]"
