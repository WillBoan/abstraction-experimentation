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
from arc_lab.solvers.program_search.substrate.library import Library, Primitive
from arc_lab.solvers.program_search.substrate.types import COLOR, GRID, INT

_GRID = GRID
_COLOR = COLOR
_INT = INT


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


READ = Primitive(name="read", param_types=(_GRID, _INT, _INT), return_type=_COLOR, impl=_read)
SET_CELL = Primitive(
    name="set_cell", param_types=(_GRID, _INT, _INT, _COLOR), return_type=_GRID, impl=_set_cell
)

#: The cell-level starting library (E2/E3): read + set_cell.
CELL_LIBRARY = Library(name="cells", primitives=(READ, SET_CELL))
