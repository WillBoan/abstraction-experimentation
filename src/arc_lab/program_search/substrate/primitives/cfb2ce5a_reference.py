"""Reference implementations for the cfb2ce5a ladder cohort's floor: a source square and the
lattice of equal-sized tiles around it.

**These are scaffolding for ONE cohort, not a considered vocabulary** — which is why the module is
named for the task rather than for a concept. (It was briefly ``tiles.py``/``TILE_PRIMITIVES``, a name
that both overstated its generality and collided conceptually with the unrelated ``tile`` primitive in
``combinators.py``.) They are high-tier percepts written to make the cfb2ce5a drafts *real* —
loadable, runnable, and checkable against the task's ground truth — so that the floor-lowering audit
has something concrete to decompose.

**Demolition status** (each decomposition validated by the promotion loop, and each one that lands
means the atom has no claim on a floor — ``tests/program_search/analysis/test_decompositions.py``):

======================== =====================================================================
``retain_colors``        the mask algebra, depth 4 — DECOMPOSED
``largest_filled_square`` ``crop_rect(g, head(filled_squares(g, 0)))``, depth 3 — DECOMPOSED
``relative_tile``        source square + per-axis lattice step + ``crop_rect``, depth 9 — DECOMPOSED
``nth_nonzero_color``    ``nth_or_default(content_colors(g, 0), i, 0)``, depth 2 — DECOMPOSED
``write_relative_tile``  the ``paste`` counterpart of ``relative_tile`` — not yet attempted
``nth_seed_source_color`` reads *pattern* at the nth *seed*'s position — not yet attempted
======================== =====================================================================

They stay registered because the committed cfb2ce5a drafts name them: a validated decomposition frees
a *new* ladder to be written over the lower floor (v5), it does not retroactively edit the old ones.

Registering them in ``BASE_PRIMITIVES`` makes them resolvable by name (what `.ladder` loading needs);
it does **not** put them in any preset's search space, since presets enumerate curated libraries.

Shared conventions with the rest of the substrate: domain errors raise and prune as ``⊥`` (there is no
meaningful no-op for "no filled square" or "tile falls off the grid"). Two deliberate departures, both
inherited from the draft spec rather than chosen: "filled" means *nonzero* rather than
*non-background* (the cfb2ce5a family draws on a literal 0 canvas), and the two ``nth_*`` perceivers
**totalize** — returning color 0 for an absent index instead of raising. That second one is a real
semantic axis, not a detail: it is invisible on in-range inputs and is exactly what made the naive
``nth`` decomposition split (hence ``nth_or_default``).
"""

from __future__ import annotations

import numpy as np

from arc_lab.core.grid import Grid
from arc_lab.program_search.substrate.library import Primitive
from arc_lab.program_search.substrate.types import COLOR, GRID, INT


def _square_origin(grid: Grid) -> tuple[int, int, int]:
    """The ``(row, col, size)`` of the largest all-nonzero square; ties break topmost then leftmost.

    Classic O(cells) DP: ``dp[i, j]`` is the side of the largest all-nonzero square whose *bottom-right*
    corner is ``(i, j)``. Scanning bottom-right corners in row-major order visits their origins in
    row-major order too (the origin is a fixed offset back), so the first corner reaching the maximum
    side is the topmost-then-leftmost origin — the tie-break the ladder's floor documents.
    """
    array = grid.array
    filled = (array != 0).astype(np.int64)
    dp = filled.copy()
    for row in range(1, dp.shape[0]):
        for col in range(1, dp.shape[1]):
            if filled[row, col]:
                dp[row, col] = 1 + min(dp[row - 1, col], dp[row, col - 1], dp[row - 1, col - 1])
    size = int(dp.max())
    if size == 0:
        raise ValueError("grid contains no nonzero cell, so no filled square")
    corners = np.argwhere(dp >= size)  # argwhere yields row-major order
    row, col = int(corners[0][0]), int(corners[0][1])
    return row - size + 1, col - size + 1, size


def _crop(grid: Grid, row: int, col: int, size: int) -> Grid:
    if row < 0 or col < 0 or row + size > grid.height or col + size > grid.width:
        raise ValueError(f"tile at {(row, col)} of size {size} falls outside a {grid.shape} grid")
    return Grid(grid.array[row : row + size, col : col + size])  # noqa: E203, RUF100


def _largest_filled_square(grid: Grid) -> Grid:
    row, col, size = _square_origin(grid)
    return _crop(grid, row, col, size)


def _relative_tile(grid: Grid, down: int, right: int) -> Grid:
    """The equal-sized tile ``down``/``right`` whole source-squares from the source square's origin."""
    row, col, size = _square_origin(grid)
    return _crop(grid, row + down * size, col + right * size, size)


def _nth_nonzero_color(grid: Grid, index: int) -> int:
    """The ``index``-th nonzero color in row-major order; color 0 when there is no such cell."""
    flat = grid.array.ravel()
    nonzero = flat[flat != 0]
    if index < 0 or index >= nonzero.size:
        return 0
    return int(nonzero[index])


def _nth_seed_source_color(pattern: Grid, seeds: Grid, index: int) -> int:
    """The color ``pattern`` holds where ``seeds``' ``index``-th nonzero cell sits.

    Half of a seed *binding*: the seed's own color is the target (``nth_nonzero_color``), and the
    color underneath it in the aligned pattern is the source. Color 0 when there is no such seed, so a
    tile carrying fewer seeds than the ladder reads degenerates to an identity recolor rather than ⊥.
    """
    if pattern.shape != seeds.shape:
        raise ValueError(f"seed lookup needs aligned grids, got {pattern.shape} and {seeds.shape}")
    rows, cols = np.nonzero(seeds.array)  # nonzero yields row-major order
    if index < 0 or index >= rows.size:
        return 0
    return int(pattern.array[rows[index], cols[index]])


def _retain_colors(grid: Grid, first: int, second: int) -> Grid:
    """Keep only cells holding ``first`` or ``second``; every other cell becomes color 0."""
    array = grid.array
    array[(array != first) & (array != second)] = 0
    return Grid(array)


def _write_relative_tile(base: Grid, anchor: Grid, tile: Grid, down: int, right: int) -> Grid:
    """Write ``tile`` into ``base`` at the whole-tile offset ``anchor``'s source square defines."""
    row, col, size = _square_origin(anchor)
    if tile.shape != (size, size):
        raise ValueError(f"tile {tile.shape} does not match the source square size {size}")
    row, col = row + down * size, col + right * size
    if row < 0 or col < 0 or row + size > base.height or col + size > base.width:
        raise ValueError(f"tile at {(row, col)} of size {size} falls outside a {base.shape} grid")
    array = base.array
    array[row : row + size, col : col + size] = tile.array  # noqa: E203, RUF100
    return Grid(array)


LARGEST_FILLED_SQUARE = Primitive(
    name="largest_filled_square",
    param_types=(GRID,),
    return_type=GRID,
    impl=_largest_filled_square,
)
RELATIVE_TILE = Primitive(
    name="relative_tile", param_types=(GRID, INT, INT), return_type=GRID, impl=_relative_tile
)
NTH_NONZERO_COLOR = Primitive(
    name="nth_nonzero_color", param_types=(GRID, INT), return_type=COLOR, impl=_nth_nonzero_color
)
NTH_SEED_SOURCE_COLOR = Primitive(
    name="nth_seed_source_color",
    param_types=(GRID, GRID, INT),
    return_type=COLOR,
    impl=_nth_seed_source_color,
)
RETAIN_COLORS = Primitive(
    name="retain_colors", param_types=(GRID, COLOR, COLOR), return_type=GRID, impl=_retain_colors
)
WRITE_RELATIVE_TILE = Primitive(
    name="write_relative_tile",
    param_types=(GRID, GRID, GRID, INT, INT),
    return_type=GRID,
    impl=_write_relative_tile,
)

CFB2CE5A_REFERENCE_PRIMITIVES = (
    LARGEST_FILLED_SQUARE,
    RELATIVE_TILE,
    NTH_NONZERO_COLOR,
    NTH_SEED_SOURCE_COLOR,
    RETAIN_COLORS,
    WRITE_RELATIVE_TILE,
)
