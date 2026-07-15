"""Cell-level primitives: read and set a single cell.

These are the L1 floor for the low-primitive-formation direction (`ONTOLOGY.md`): a grid as
a mapping from coordinates to colors, manipulated one cell at a time. Coordinates are plain
``Int``s (row, col) — no ``Coord`` type — kept in bounds by the task-mined coordinate
constants (see `Enumerate(coord_ints=True)`); an out-of-range index simply raises and the
candidate is discarded during search.

Unlike ``with_cell`` folded over a comprehension (the general size-general construction),
these compose directly as typed grid transforms, so they need no AST lambda — just the
``Param``/template machinery already in place. `swap_cells` is their first target abstraction.
"""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.program_search.substrate.library import Library, Primitive, Value
from arc_lab.program_search.substrate.types import COLOR, GRID, INT, list_type

_GRID = GRID
_COLOR = COLOR
_INT = INT
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


def _from_cells(width: int, height: int, cells: Value) -> Grid:
    """The inverse of :func:`_cells`: unflatten ``cells`` row-major into a ``height x width`` grid."""
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


READ = Primitive(name="read", param_types=(_GRID, _INT, _INT), return_type=_COLOR, impl=_read)
SET_CELL = Primitive(
    name="set_cell", param_types=(_GRID, _INT, _INT, _COLOR), return_type=_GRID, impl=_set_cell
)
CELLS = Primitive(name="cells", param_types=(_GRID,), return_type=_COLOR_LIST, impl=_cells)
FROM_CELLS = Primitive(
    name="from_cells",
    param_types=(_INT, _INT, _COLOR_LIST),
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

#: The cell-level starting library (E2/E3): read + set_cell. Deliberately excludes the target
#: primitives (`swap_cells`/`move_cell`) — those exist to be *withheld* and re-derived.
CELL_LIBRARY = Library(name="cells", primitives=(READ, SET_CELL))
