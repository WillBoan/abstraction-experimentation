"""Region *plurality*, *measures*, and the way *back* — the three capabilities the substrate lacked.

Before this bundle, regions were a one-way street: one mask in (``mask_by_color`` / ``nonbg_mask`` /
``bbox_mask``), one cropped grid out (``crop_to_mask``, which discards the origin). Nothing produced
*many* regions, nothing could measure one, and nothing could write a patch back. That is why
cfb2ce5a's floor had to hand-roll `largest_filled_square` (plurality + measure fused),
`relative_tile` (locate + crop) and `write_relative_tile` (locate + paste) as single atoms.

**Producers generate candidates; predicates and measures select.** Keeping the "what counts as an
object" judgment OUT of the producer is what leaves the perception in the *composition*, where a
ladder can climb it. ``filled_squares`` is the deliberate exception, and it is a real tradeoff rather
than an oversight: all squares of an n x n grid is ``n(n+1)(2n+1)/6`` (9,455 at ARC's 30x30), so a
pure candidate generator is not affordable at full size. Both spellings ship, so the
decomposability-vs-tractability knob is measurable rather than assumed.

**"Filled" is a parameter, never a convention.** Every predicate here takes its background color
explicitly, so ``filled_squares(g, 0)`` (a literal-0 canvas) and
``filled_squares(g, most_common_color(g))`` (the general reading) are two *compositions* of one
primitive rather than two atoms -- which is what lets a ladder learn the second from the first as a
genuine one-level rung (``perceive.py``'s "turn literal constants into derived values" idiom).

Return types follow one rule: **the most specific type that losslessly represents the family.**
Rectangular decompositions are ``list[rect]`` (O(1) each, and they compose with the addressing
algebra); connected components are ``list[mask]``, because a component genuinely is not a rectangle.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from arc_lab.core.geometry import Coord, Offset, Rect
from arc_lab.core.grid import Grid
from arc_lab.core.mask import Mask
from arc_lab.program_search.substrate.library import Primitive
from arc_lab.program_search.substrate.types import (
    COLOR,
    COORD,
    GRID,
    INT,
    MASK,
    RECT,
    list_type,
)


def _bounds(rect: Rect) -> tuple[int, int, int, int]:
    """``(row_lo, row_hi_exclusive, col_lo, col_hi_exclusive)``."""
    origin, extent = rect.origin, rect.extent
    return origin.row, origin.row + extent.d_row, origin.col, origin.col + extent.d_col


def _within(grid: Grid, rect: Rect) -> bool:
    row_lo, row_hi, col_lo, col_hi = _bounds(rect)
    return row_lo >= 0 and col_lo >= 0 and row_hi <= grid.height and col_hi <= grid.width


# -- measures --------------------------------------------------------------------------------------


def _mask_area(mask: Mask) -> int:
    return int(np.count_nonzero(mask.array))


def _bbox(mask: Mask) -> Rect:
    """The tight bounding :class:`Rect` of the selected cells; an empty mask raises (no bbox)."""
    rows, cols = np.nonzero(mask.array)
    if rows.size == 0:
        raise ValueError("mask selects no cells, so it has no bounding box")
    row_lo, row_hi = int(rows.min()), int(rows.max())
    col_lo, col_hi = int(cols.min()), int(cols.max())
    return Rect(Coord(row_lo, col_lo), Offset(row_hi - row_lo + 1, col_hi - col_lo + 1))


# -- bridges and elims -----------------------------------------------------------------------------


def _rect_clip(grid: Grid, rect: Rect) -> Rect:
    """``rect`` intersected with ``grid``'s bounds; raises when they do not overlap at all.

    The explicit half of "a Rect may hang off the edge": representing the overhang is legal, and
    reducing it to what actually exists is a named step rather than a silent one.
    """
    row_lo, row_hi, col_lo, col_hi = _bounds(rect)
    row_lo, row_hi = max(0, row_lo), min(grid.height, row_hi)
    col_lo, col_hi = max(0, col_lo), min(grid.width, col_hi)
    if row_lo >= row_hi or col_lo >= col_hi:
        raise ValueError(f"rect {rect} does not overlap a {grid.shape} grid")
    return Rect(Coord(row_lo, col_lo), Offset(row_hi - row_lo, col_hi - col_lo))


def _rect_to_mask(grid: Grid, rect: Rect) -> Mask:
    """``rect`` as a grid-shaped selection, clipped to the grid (see :func:`_rect_clip`)."""
    clipped = _rect_clip(grid, rect)
    row_lo, row_hi, col_lo, col_hi = _bounds(clipped)
    out = np.zeros(grid.shape, dtype=np.bool_)
    out[row_lo:row_hi, col_lo:col_hi] = True
    return Mask(out)


def _crop_rect(grid: Grid, rect: Rect) -> Grid:
    """The sub-grid ``rect`` names. Out of bounds is a domain error, NOT a silent clip: a caller
    that wants the overlap says so with ``rect_clip``."""
    if not _within(grid, rect):
        raise ValueError(f"rect {rect} is not inside a {grid.shape} grid")
    row_lo, row_hi, col_lo, col_hi = _bounds(rect)
    return Grid(grid.array[row_lo:row_hi, col_lo:col_hi])


def _paste(base: Grid, patch: Grid, at: Coord) -> Grid:
    """Write ``patch`` into ``base`` with its top-left at ``at`` -- the missing region elim.

    The counterpart to ``crop_rect``: together they make crop -> transform -> put-back expressible,
    which ``crop_to_mask`` alone never was (it discards the origin).
    """
    rect = Rect(at, Offset(patch.height, patch.width))
    if not _within(base, rect):
        raise ValueError(f"patch {patch.shape} at {at} does not fit a {base.shape} grid")
    row_lo, row_hi, col_lo, col_hi = _bounds(rect)
    array = base.array  # a writable copy: `paste` must not mutate its caller's grid
    array[row_lo:row_hi, col_lo:col_hi] = patch.array
    return Grid(array)


# -- region producers ------------------------------------------------------------------------------


def _quadrants(grid: Grid) -> tuple[Rect, ...]:
    """The four quadrants, reading order (NW, NE, SW, SE). Odd sizes split with the larger half
    first, so the four always tile the grid exactly."""
    top = (grid.height + 1) // 2
    left = (grid.width + 1) // 2
    spans = (
        (0, top, 0, left),
        (0, top, left, grid.width),
        (top, grid.height, 0, left),
        (top, grid.height, left, grid.width),
    )
    quadrants: list[Rect] = []
    for row_lo, row_hi, col_lo, col_hi in spans:
        if row_lo < row_hi and col_lo < col_hi:  # a 1-wide grid has no east half
            quadrants.append(Rect(Coord(row_lo, col_lo), Offset(row_hi - row_lo, col_hi - col_lo)))
    return tuple(quadrants)


def _squares_of_size(grid: Grid, size: int) -> tuple[Rect, ...]:
    """Every axis-aligned ``size`` x ``size`` square, row-major. O(n^2) -- the affordable form."""
    if size < 1:
        raise ValueError(f"square size must be at least 1, got {size}")
    extent = Offset(size, size)
    return tuple(
        Rect(Coord(row, col), extent)
        for row in range(grid.height - size + 1)
        for col in range(grid.width - size + 1)
    )


def _squares(grid: Grid) -> tuple[Rect, ...]:
    """Every axis-aligned square of every size, largest first then row-major.

    **O(n^3) results** (``n(n+1)(2n+1)/6`` -- 9,455 on a 30x30 grid). The honest pure candidate
    generator, and priced accordingly: prefer ``squares_of_size`` or ``filled_squares`` unless the
    exhaustive set is genuinely wanted.
    """
    largest = min(grid.height, grid.width)
    out: list[Rect] = []
    for size in range(largest, 0, -1):
        out.extend(_squares_of_size(grid, size))
    return tuple(out)


def _filled(grid: Grid, background: int) -> npt.NDArray[np.bool_]:
    """The cells that are not the background — the one place "filled" is decided, from a parameter."""
    filled: npt.NDArray[np.bool_] = grid.array != background
    return filled


def _square_sides(filled: npt.NDArray[np.bool_]) -> npt.NDArray[np.int64]:
    """``dp[i, j]`` = side of the largest all-filled square with bottom-right corner ``(i, j)``."""
    dp = filled.astype(np.int64)
    for row in range(1, dp.shape[0]):
        for col in range(1, dp.shape[1]):
            if filled[row, col]:
                dp[row, col] = 1 + min(dp[row - 1, col], dp[row, col - 1], dp[row - 1, col - 1])
    return dp


def _filled_squares(grid: Grid, background: int) -> tuple[Rect, ...]:
    """Every all-``!= background`` square, largest first then row-major (ties topmost-leftmost).

    Ordering is the contract: ``head(filled_squares(g, bg))`` is the largest filled square, so the
    percept cfb2ce5a's floor spelled as one atom becomes a composition.
    """
    dp = _square_sides(_filled(grid, background))
    largest = int(dp.max()) if dp.size else 0
    out: list[Rect] = []
    for size in range(largest, 0, -1):
        extent = Offset(size, size)
        for row in range(grid.height - size + 1):
            for col in range(grid.width - size + 1):
                if dp[row + size - 1, col + size - 1] >= size:
                    out.append(Rect(Coord(row, col), extent))
    return tuple(out)


def _maximal_filled_squares(grid: Grid, background: int) -> tuple[Rect, ...]:
    """The filled squares not contained in a larger one -- "the objects", not every sub-square."""
    covered = np.zeros(grid.shape, dtype=np.bool_)
    out: list[Rect] = []
    for candidate in _filled_squares(grid, background):
        row_lo, row_hi, col_lo, col_hi = _bounds(candidate)
        if covered[row_lo:row_hi, col_lo:col_hi].all():
            continue  # every cell already claimed by a larger square: not maximal
        covered[row_lo:row_hi, col_lo:col_hi] = True
        out.append(candidate)
    return tuple(out)


def _connected_regions(grid: Grid, background: int) -> tuple[Mask, ...]:
    """The 4-connected same-color components of the non-background cells, largest first.

    4-connectivity is the default reading; an 8-connected sibling is a separate primitive if a task
    ever needs one, rather than a flag search would have to enumerate.
    """
    array = grid.array
    height, width = array.shape
    seen = np.zeros((height, width), dtype=np.bool_)
    components: list[tuple[int, Mask]] = []
    for start_row in range(height):
        for start_col in range(width):
            color = int(array[start_row, start_col])
            if color == background or seen[start_row, start_col]:
                continue
            cells = np.zeros((height, width), dtype=np.bool_)
            stack = [(start_row, start_col)]
            seen[start_row, start_col] = True
            while stack:
                row, col = stack.pop()
                cells[row, col] = True
                for next_row, next_col in (
                    (row - 1, col),
                    (row + 1, col),
                    (row, col - 1),
                    (row, col + 1),
                ):
                    if (
                        0 <= next_row < height
                        and 0 <= next_col < width
                        and not seen[next_row, next_col]
                        and int(array[next_row, next_col]) == color
                    ):
                        seen[next_row, next_col] = True
                        stack.append((next_row, next_col))
            components.append((int(np.count_nonzero(cells)), Mask(cells)))
    # Largest first; discovery order (row-major) breaks ties, so the result is deterministic.
    order = sorted(range(len(components)), key=lambda i: (-components[i][0], i))
    return tuple(components[i][1] for i in order)


def _content_coords(grid: Grid, background: int) -> tuple[Coord, ...]:
    """The positions of the non-background cells, row-major -- a grid's geometry AS a list.

    The gap this fills: ``cells``/``palette`` were the only grid-to-list producers and both discard
    position, so nothing could enumerate *where* the content is.
    """
    rows, cols = np.nonzero(_filled(grid, background))
    return tuple(Coord(int(row), int(col)) for row, col in zip(rows, cols, strict=True))


def _content_colors(grid: Grid, background: int) -> tuple[int, ...]:
    """The colors of the non-background cells, row-major -- **index-aligned** with
    :func:`_content_coords`.

    That alignment is the whole point, and what distinguishes this from the two existing
    color-list producers: they are three different things.

    ==========================  =================  ==========  ============  ==========
    producer                    contents           order       duplicates    background
    ==========================  =================  ==========  ============  ==========
    ``palette(g)``              distinct colors    ascending   no            included
    ``cells(g)``                every cell         row-major   yes           included
    ``content_colors(g, bg)``   non-bg cells       row-major   yes           excluded
    ==========================  =================  ==========  ============  ==========

    So ``palette`` is roughly ``sort(unique(cells))`` and this is ``cells`` minus the background --
    no redundancy. Being a *parallel projection of one traversal* alongside ``content_coords`` is
    what makes ``nth`` over either meaningful (and what a fused ``Cell`` list would combine).
    """
    array = grid.array
    return tuple(int(color) for color in array[_filled(grid, background)].ravel())


MASK_AREA = Primitive(name="mask_area", param_types=(MASK,), return_type=INT, impl=_mask_area)
BBOX = Primitive(name="bbox", param_types=(MASK,), return_type=RECT, impl=_bbox)
RECT_CLIP = Primitive(name="rect_clip", param_types=(GRID, RECT), return_type=RECT, impl=_rect_clip)
RECT_TO_MASK = Primitive(
    name="rect_to_mask", param_types=(GRID, RECT), return_type=MASK, impl=_rect_to_mask
)
CROP_RECT = Primitive(name="crop_rect", param_types=(GRID, RECT), return_type=GRID, impl=_crop_rect)
PASTE = Primitive(name="paste", param_types=(GRID, GRID, COORD), return_type=GRID, impl=_paste)
QUADRANTS = Primitive(
    name="quadrants", param_types=(GRID,), return_type=list_type(RECT), impl=_quadrants
)
SQUARES_OF_SIZE = Primitive(
    name="squares_of_size",
    param_types=(GRID, INT),
    return_type=list_type(RECT),
    impl=_squares_of_size,
)
SQUARES = Primitive(name="squares", param_types=(GRID,), return_type=list_type(RECT), impl=_squares)
FILLED_SQUARES = Primitive(
    name="filled_squares",
    param_types=(GRID, COLOR),
    return_type=list_type(RECT),
    impl=_filled_squares,
)
MAXIMAL_FILLED_SQUARES = Primitive(
    name="maximal_filled_squares",
    param_types=(GRID, COLOR),
    return_type=list_type(RECT),
    impl=_maximal_filled_squares,
)
CONNECTED_REGIONS = Primitive(
    name="connected_regions",
    param_types=(GRID, COLOR),
    return_type=list_type(MASK),
    impl=_connected_regions,
)
CONTENT_COORDS = Primitive(
    name="content_coords",
    param_types=(GRID, COLOR),
    return_type=list_type(COORD),
    impl=_content_coords,
)
CONTENT_COLORS = Primitive(
    name="content_colors",
    param_types=(GRID, COLOR),
    return_type=list_type(COLOR),
    impl=_content_colors,
)

REGION_PRIMITIVES = (
    MASK_AREA,
    BBOX,
    RECT_CLIP,
    RECT_TO_MASK,
    CROP_RECT,
    PASTE,
    QUADRANTS,
    SQUARES_OF_SIZE,
    SQUARES,
    FILLED_SQUARES,
    MAXIMAL_FILLED_SQUARES,
    CONNECTED_REGIONS,
    CONTENT_COORDS,
    CONTENT_COLORS,
)
