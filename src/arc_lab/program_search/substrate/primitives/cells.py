"""Cell-level primitives: read and set a single cell.

These are the L1 floor for the low-primitive-formation direction (`ONTOLOGY.md`): a grid as
a mapping from coordinates to colors, manipulated one cell at a time. An out-of-range index
simply raises and the candidate is discarded during search.

**Each operation ships in two flavors**: over loose ``Int``s (``read``, ``set_cell``, ...) and over
:class:`~arc_lab.core.geometry.Coord` (``read_color_at_coord``, ...). Neither supersedes the other --
see the flavor note above the coord family for why both exist and why a flavor must be chosen for the
whole family at once.

Unlike ``with_cell`` folded over a comprehension (the general size-general construction),
these compose directly as typed grid transforms, so they need no AST lambda — just the
``Param``/template machinery already in place. `swap_cells` is their first target abstraction.
"""

from __future__ import annotations

from arc_lab.core.geometry import Coord, Offset
from arc_lab.core.grid import Grid
from arc_lab.program_search.substrate.library import Library, Primitive, Value
from arc_lab.program_search.substrate.types import (
    COLOR,
    COORD,
    GRID,
    INT,
    OFFSET,
    list_type,
)

_GRID = GRID
_COLOR = COLOR
_INT = INT
_OFFSET = OFFSET
_COORD = COORD
_COLOR_LIST = list_type(_COLOR)


def _read(grid: Grid, row: int, col: int) -> int:
    """The color at (row, col); raises IndexError out of bounds (caught by search)."""
    if row < 0 or col < 0:  # forbid numpy's negative wraparound — coords are non-negative
        raise IndexError((row, col))
    return int(grid.array[row, col])


def _set_cell(grid: Grid, row: int, col: int, color: int) -> Grid:
    """A copy of ``grid`` with (row, col) recolored; raises IndexError out of bounds."""
    if row < 0 or col < 0:
        raise IndexError((row, col))
    array = grid.array.copy()
    array[row, col] = color
    return Grid(array)


def _cells(grid: Grid) -> Value:
    """The grid's colors, flattened row-major — the list-vocabulary counterpart to ``build_grid``'s
    per-cell coordinate function (§3 scope/row-major ordering)."""
    return tuple(color for row in grid.to_list() for color in row)


def _from_cells(size: Offset, cells: Value) -> Grid:
    """The inverse of :func:`_cells`: unflatten ``cells`` row-major into a grid of extent ``size``.

    ``size`` is an :class:`Offset` (an extent), so the two dimensions travel together and cannot be
    silently transposed by the enumerator -- ``from_cells`` is the one place a height/width swap
    produces a *valid* grid of the wrong shape rather than an error.
    """
    height, width = size.d_row, size.d_col
    if not isinstance(cells, tuple):
        raise TypeError(f"from_cells expects a list, got {type(cells).__name__}")
    if width < 0 or height < 0:
        raise ValueError(f"from_cells dimensions must be non-negative, got {(width, height)}")
    if len(cells) != width * height:
        raise ValueError(f"from_cells got {len(cells)} cells, expected {width * height}")
    rows: list[list[int]] = []
    for i in range(height):
        row: list[int] = []
        for color in cells[i * width : (i + 1) * width]:  # noqa: E203, RUF100
            if not isinstance(color, int) or isinstance(color, bool):
                raise TypeError(f"from_cells expects a list of colors, got {type(color).__name__}")
            row.append(color)
        rows.append(row)
    return Grid.from_list(rows)


def _swap_cells(grid: Grid, row_a: int, col_a: int, row_b: int, col_b: int) -> Grid:
    """Exchange the colors at (row_a, col_a) and (row_b, col_b).

    Hand-shipped so it can serve as a withheld study *target* (a study's L3 = L1 + targets needs
    the target to exist as a primitive); the re-derivation experiments (E2 lineage) keep it out of
    their starting libraries. Derivable from ``read`` + ``set_cell`` by re-reading the original grid.
    """
    color_a = _read(grid, row_a, col_a)
    color_b = _read(grid, row_b, col_b)
    return _set_cell(_set_cell(grid, row_a, col_a, color_b), row_b, col_b, color_a)


def _move_cell(grid: Grid, row_a: int, col_a: int, row_b: int, col_b: int) -> Grid:
    """Relocate (row_a, col_a)'s color to (row_b, col_b), clearing the source to 0.

    Same target-not-starting-vocabulary status as :func:`_swap_cells`. The source clears to color 0
    (not "background") so it stays derivable from ``read`` + ``set_cell`` + a ``0`` constant.
    """
    color = _read(grid, row_a, col_a)
    return _set_cell(_set_cell(grid, row_b, col_b, color), row_a, col_a, 0)


# -- the coord-flavored family -----------------------------------------------------------------------
#
# The SAME four operations over :class:`Coord` instead of loose ints. Added ALONGSIDE the int
# versions rather than replacing them, for two independent reasons:
#
# 1. al14's rung computes its coordinates (``sub(n, 1)``), so wrapping them in ``coord(...)`` takes
#    ``move_cell_up`` from d_i=3 to 4 -- past the ``depth_limit: 3`` it declares -- and al14 carries
#    pinned probe expectations (the 2026-07-21 collapse/collision finding). A literal cannot rescue a
#    *computed* coordinate, so replacing ``read`` would have forced a research artifact to move.
# 2. Neither flavor is "better": how coordinate-shaped a primitive should be is a per-experiment
#    judgment call, and having both is what makes that a knob instead of a commitment.
#
# **All four ship together, deliberately.** ``swap_cells``/``move_cell`` exist to be *withheld* study
# targets, rederivable from their own floor's ``read``/``set_cell`` (``CELL_FLOOR_WITH_TARGETS``). A
# half-split family -- coord targets over an int floor -- would silently break that derivability, so
# the flavor is a property of the whole family.


def _read_color_at_coord(grid: Grid, at: Coord) -> int:
    return _read(grid, at.row, at.col)


def _set_color_at_coord(grid: Grid, at: Coord, color: int) -> Grid:
    return _set_cell(grid, at.row, at.col, color)


def _swap_cells_at_coords(grid: Grid, a: Coord, b: Coord) -> Grid:
    return _swap_cells(grid, a.row, a.col, b.row, b.col)


def _move_cell_between_coords(grid: Grid, source: Coord, target: Coord) -> Grid:
    return _move_cell(grid, source.row, source.col, target.row, target.col)


READ = Primitive(name="read", param_types=(_GRID, _INT, _INT), return_type=_COLOR, impl=_read)
SET_CELL = Primitive(
    name="set_cell", param_types=(_GRID, _INT, _INT, _COLOR), return_type=_GRID, impl=_set_cell
)
CELLS = Primitive(name="cells", param_types=(_GRID,), return_type=_COLOR_LIST, impl=_cells)
FROM_CELLS = Primitive(
    name="from_cells",
    param_types=(_OFFSET, _COLOR_LIST),
    return_type=_GRID,
    impl=_from_cells,
)
SWAP_CELLS = Primitive(
    name="swap_cells",
    param_types=(_GRID, _INT, _INT, _INT, _INT),
    return_type=_GRID,
    impl=_swap_cells,
)
MOVE_CELL = Primitive(
    name="move_cell",
    param_types=(_GRID, _INT, _INT, _INT, _INT),
    return_type=_GRID,
    impl=_move_cell,
)

READ_COLOR_AT_COORD = Primitive(
    name="read_color_at_coord",
    param_types=(_GRID, _COORD),
    return_type=_COLOR,
    impl=_read_color_at_coord,
)
SET_COLOR_AT_COORD = Primitive(
    name="set_color_at_coord",
    param_types=(_GRID, _COORD, _COLOR),
    return_type=_GRID,
    impl=_set_color_at_coord,
)
SWAP_CELLS_AT_COORDS = Primitive(
    name="swap_cells_at_coords",
    param_types=(_GRID, _COORD, _COORD),
    return_type=_GRID,
    impl=_swap_cells_at_coords,
)
MOVE_CELL_BETWEEN_COORDS = Primitive(
    name="move_cell_between_coords",
    param_types=(_GRID, _COORD, _COORD),
    return_type=_GRID,
    impl=_move_cell_between_coords,
)

#: The cell-level starting library (E2/E3): read + set_cell. Deliberately excludes the target
#: primitives (`swap_cells`/`move_cell`) — those exist to be *withheld* and re-derived.
CELL_LIBRARY = Library(name="cells", primitives=(READ, SET_CELL))

#: The coord-flavored counterpart, same contract: the accessors, targets withheld. Kept separate
#: from `CELL_LIBRARY` so a study picks ONE flavor -- mixing them breaks the derivability the
#: withheld targets depend on (see the flavor note above).
COORD_CELL_LIBRARY = Library(
    name="coord-cells", primitives=(READ_COLOR_AT_COORD, SET_COLOR_AT_COORD)
)

#: Every cell primitive, both flavors -- the registry's view.
CELL_PRIMITIVES = (
    READ,
    SET_CELL,
    CELLS,
    FROM_CELLS,
    SWAP_CELLS,
    MOVE_CELL,
    READ_COLOR_AT_COORD,
    SET_COLOR_AT_COORD,
    SWAP_CELLS_AT_COORDS,
    MOVE_CELL_BETWEEN_COORDS,
)
