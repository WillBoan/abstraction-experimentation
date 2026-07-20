"""``al14-cell-row-grid``: the dimensional-lift tower -- cell, then row, then grid.

L0 {read, set_cell, sub} -> move_cell_up -> move_row_up -> move_grid_up -> top. Each rung is the one
below applied across the next dimension: a row-move IS three cell-moves, a grid-move IS three
row-moves. The nesting is not decoration -- it is what "a row is many cells" actually means.

**Why this ladder matters.** Every other ladder in the batch nests its rungs shallowly, so raw depth
grows by roughly +1 per level and the batch's depth compression tops out around 3.5x with validity
windows of width 1. Here each rung nests three copies of the one below *on its deepest path*, so raw
depth **multiplies**: 3 -> 9 -> 27 -> 54. That gives **18x depth compression** at a pinned
``depth_limit`` of 3, and a validity window of **width 6** -- the first ladder where budget is a
genuinely sweepable axis rather than a single honest cell.

Two deliberate limitations. The abstractions are **width-specific** (a 3-wide ``move_row_up`` does
not work on 4-wide grids) -- the opposite of the size-general ``build_grid`` abstractions E5-E9
chased, and worth contrasting against. And the indices are INT constants, so ``finite-enumerate``
over a wide integer domain is the cost risk to watch.

The original formulation (design conversation, 2026-07-20) had ``read_row``/``write_row`` returning a
``List``. That is not expressible over a cell-level floor -- building a list needs a constructor, a
width, and iteration -- and adding those makes the floor higher-order, at which point
``compositional_depth`` treats ``Lam`` as a leaf and the sandwich cannot be statically verified at
all. Nesting fixed-width cell-moves keeps the same dimensional-lift idea and stays first-order.
"""

from __future__ import annotations

from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.model.learn_spec import LearnSpec
from arc_lab.program_search.ladders.registry._common import spec_from_testbed
from arc_lab.program_search.ladders.spec import DemonstrationKind, LadderSpec
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Apply, Const, Input, Param, Program
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import COLOR, GRID, INT
from arc_lab.taskgen.ladders import LadderTestbed, RungTasks, TopTasks

NAME = "al14-cell-row-grid"
#: Grid shape the row/grid abstractions are specialised to. Rows start at 1 so moving up stays in
#: bounds (a cell at y=0 has nowhere to go).
WIDTH, HEIGHT = 3, 4
_COLS = tuple(range(WIDTH))  # a row-move touches every column
_ROWS = tuple(range(1, HEIGHT))  # row 0 has nowhere to move up to
_FULL = DemonstrationKind.FULL_SOLUTION


def _a(name: str, *args: Program) -> Apply:
    return Apply(name, tuple(args))


FLOOR = Library(
    name="al14-L0",
    primitives=tuple(BASE_PRIMITIVES[n] for n in ("read", "set_cell", "sub")),
)
#: Indices are (row, col) -- `read`/`set_cell` take the ROW first. "Up" decrements the row.
_G, _ROW, _COL = Param(0, GRID), Param(1, INT), Param(2, INT)

#: r1 -- move one cell up, blanking where it came from (d=3).
MOVE_CELL_UP = _a(
    "set_cell",
    _a("set_cell", _G, _a("sub", _ROW, Const(1, INT)), _COL, _a("read", _G, _ROW, _COL)),
    _ROW,
    _COL,
    Const(0, COLOR),
)


def _nest(inner: Program, name: str, indices: tuple[int, ...], extra: Program | None) -> Program:
    """Apply ``name`` once per index, each call wrapping the previous -- the deepest-path nesting
    that makes raw depth multiply rather than add."""
    out = inner
    for i in indices:
        args = (out, Const(i, INT)) if extra is None else (out, extra, Const(i, INT))
        out = _a(name, *args)
    return out


#: r2 -- a row-move IS the cell-move applied across every column (d=3 over L_1).
MOVE_ROW_UP = _nest(Param(0, GRID), "move_cell_up", _COLS, Param(1, INT))
#: r3 -- a grid-move IS the row-move applied across every row (d=3 over L_2).
MOVE_GRID_UP = _nest(Param(0, GRID), "move_row_up", _ROWS, None)
#: Top -- self-composition, which is what pushes d_raw to 54.
TOP = _a("move_grid_up", _a("move_grid_up", Input()))

_RUNGS = (
    ("move_cell_up", MOVE_CELL_UP),
    ("move_row_up", MOVE_ROW_UP),
    ("move_grid_up", MOVE_GRID_UP),
)
REFERENCE_BUDGET = Budget(depth_limit=3, max_arity=4, max_pool=2000)


def testbed() -> LadderTestbed:
    """Grids are HEIGHT x WIDTH throughout, since the row/grid rungs are specialised to that shape.
    r1's free params (x, y) are fixed within a task and varied across tasks."""
    return LadderTestbed(
        floor=FLOOR,
        rungs=(
            RungTasks(
                name="move_cell_up",
                template=MOVE_CELL_UP,
                train_args=((1, 0), (2, 1)),  # (row, col), row >= 1
                heldout_args=((3, 2),),
                rows=HEIGHT,
                cols=WIDTH,
            ),
            RungTasks(
                name="move_row_up",
                template=MOVE_ROW_UP,
                train_args=((2,), (3,)),
                heldout_args=((1,),),
                rows=HEIGHT,
                cols=WIDTH,
            ),
            RungTasks(
                name="move_grid_up",
                template=MOVE_GRID_UP,
                train_args=((), ()),
                heldout_args=((),),
                rows=HEIGHT,
                cols=WIDTH,
            ),
        ),
        top=TopTasks(solutions=(TOP,), heldout_solutions=(TOP,), rows=HEIGHT, cols=WIDTH),
        note=(
            "al14-cell-row-grid: {read, set_cell, sub} -> move_cell_up -> move_row_up -> "
            "move_grid_up -> top. Dimensional lift; raw depth multiplies (3->9->27->54)."
        ),
    )


def build() -> LadderSpec:
    reference_config = Config(
        library=FLOOR,
        search_engine=BottomUpSearchEngine(
            constant_sources=("finite-enumerate",),  # INT indices + the blanking COLOR
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=REFERENCE_BUDGET,
        learn=LearnSpec(learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()), iterations=6),
    )
    return spec_from_testbed(
        NAME,
        reference_config=reference_config,
        rungs=tuple((n, t, _FULL) for n, t in _RUNGS),
        top_solutions=(TOP,),
    )
