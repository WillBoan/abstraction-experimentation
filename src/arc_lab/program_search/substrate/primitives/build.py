"""The cell-render floor: ``build_grid`` and the coordinate arithmetic it composes.

``build_grid(h, w, f)`` constructs an ``h x w`` grid by evaluating the coordinate->color function
``f`` at every cell — the reified quantifier that makes cell-level geometry *size-general*: one
small program re-derives ``rot90`` on any grid, via coordinate arithmetic rather than an opaque
numpy transform. ``f`` is a *curried* lambda (``Lam(Lam(body))``, Stitch-standard): applied to the
row, then the column, so ``body`` sees the row as ``$1`` and the column as ``$0``.

These are the D4-rederivation clique (`ONTOLOGY.md`): ``build_grid`` (the L1 render), ``width`` /
``height`` (L1 dimension perceivers), and ``sub`` (L0 integer arithmetic) — enough to express any
D4 member as ``build_grid(dims, lam(lam(read(input, <coord expr>, <coord expr>))))``. ``read`` is
reused from `cells.py`. Nothing here is wired into a locked solver; it's the substrate for a future
`BuildGridSearch` (the open-term body search) and the pixels→D4 experiment.
"""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.core.task import TrainExamples
from arc_lab.program_search.substrate.library import (
    Closure,
    Library,
    Primitive,
    RawContext,
    Value,
)
from arc_lab.program_search.substrate.primitives.cells import READ, SET_CELL
from arc_lab.program_search.substrate.types import COLOR, GRID, INT, ArrowType

_GRID = GRID
_INT = INT
#: ``build_grid``'s coordinate function is curried: row -> (col -> color).
_CELL_FN = ArrowType((_INT,), ArrowType((_INT,), COLOR))


def _width(grid: Grid) -> int:
    return int(grid.array.shape[1])


def _height(grid: Grid) -> int:
    return int(grid.array.shape[0])


def _sub(a: int, b: int) -> int:
    return a - b


def _add(a: int, b: int) -> int:
    return a + b


def _mul(a: int, b: int) -> int:
    return a * b


def _build_grid(height: int, width: int, fn: Value) -> Grid:
    """An ``height x width`` grid whose cell (i, j) is ``fn(i)(j)`` -- the lambda, applied per cell.

    ``fn`` is the curried coordinate→color function: ``fn(i)`` binds the row (returning a closure
    over the column), and applying *that* to ``j`` yields the cell's color. Bad coordinates raise
    inside ``read`` and the whole candidate is discarded during search.
    """
    if not isinstance(fn, Closure):
        raise TypeError(f"build_grid expects a function value, got {type(fn).__name__}")
    if height < 0 or width < 0:
        raise ValueError(f"build_grid dimensions must be non-negative, got {(height, width)}")
    rows: list[list[int]] = []
    for i in range(height):
        row_fn = fn(i)  # apply to the row → a closure awaiting the column
        if not isinstance(row_fn, Closure):
            raise TypeError("build_grid's function must be curried, i.e. lam(lam(...))")
        row: list[int] = []
        for j in range(width):
            color = row_fn(j)
            if not isinstance(color, int):
                raise TypeError(f"build_grid body must yield a color, got {type(color).__name__}")
            row.append(color)
        rows.append(row)
    return Grid.from_list(rows)


def _build_grid_body_sampler(
    train_examples: TrainExamples, sibling_arg_values: tuple[Value, ...]
) -> tuple[tuple[RawContext, ...], tuple[Value, ...] | None]:
    """``build_grid``'s body search: one context per training-output cell, fully propagated.

    Contexts pair each training input with an output-cell coordinate binding ``(row, col)`` (row
    outer/``$1``, col inner/``$0`` — §3 scope ordering); the aligned target is that cell's color, so
    the body search extracts exactly the coordinate→color functions that reproduce the outputs.
    Contexts come from the training pairs' *output* dims, not the ``h``/``w`` sibling arguments —
    ``sibling_arg_values`` is unused here.
    """
    contexts: list[RawContext] = []
    target: list[Value] = []
    for example in train_examples:
        if example.output is None:
            continue
        cells = example.output.to_list()
        for row in range(example.output.height):
            for col in range(example.output.width):
                contexts.append((example.input, (row, col)))
                target.append(cells[row][col])
    return tuple(contexts), tuple(target)


WIDTH = Primitive(name="width", param_types=(_GRID,), return_type=_INT, impl=_width)
HEIGHT = Primitive(name="height", param_types=(_GRID,), return_type=_INT, impl=_height)
SUB = Primitive(name="sub", param_types=(_INT, _INT), return_type=_INT, impl=_sub)
ADD = Primitive(name="add", param_types=(_INT, _INT), return_type=_INT, impl=_add)
MUL = Primitive(name="mul", param_types=(_INT, _INT), return_type=_INT, impl=_mul)
BUILD_GRID = Primitive(
    name="build_grid",
    param_types=(_INT, _INT, _CELL_FN),
    return_type=_GRID,
    impl=_build_grid,
    body_sampler=_build_grid_body_sampler,
)

#: The cell-render floor: cells (read / set_cell) + dimension perceivers + arithmetic + build_grid.
#: `sub` alone is the D4-rederivation clique (reflection is (n - k) - 1); `add`/`mul` are held out here.
BUILD_LIBRARY = Library(name="build", primitives=(READ, SET_CELL, WIDTH, HEIGHT, SUB, BUILD_GRID))

#: The *affine* coordinate grammar: the cell floor plus the whole (INT, INT) -> INT family
#: (`sub` + `add` + `mul`), so a primitive-driven `BuildGridSearch` composes a*x+b coordinate maps
#: -- an honest, wider search than reflection-only `sub`. The grammar axis of the E8/E9 matrix.
BUILD_AFFINE_LIBRARY = Library(
    name="build-affine",
    primitives=(READ, SET_CELL, WIDTH, HEIGHT, SUB, ADD, MUL, BUILD_GRID),
)
