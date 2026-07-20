"""``al16-layout-nest``: nested layouts where each rung arranges the one below on a new axis.

The second certified-clean design from the 2026-07-20 rebuild. Where al15 alternates a combine op
with a modifier, this one alternates the combine *axis* -- and, crucially, each rung's arrangement
is entangled with the rung below (``n2 = concat_v(n1 g, n1 g)`` wraps ``n1``), so it is NOT a free-
standing universal doubler. That is precisely why it does NOT telescope: the al3/al7 collapse needed
a self-contained doubler ``D`` with ``D(D(g))`` reaching two rungs up; here the "doubler" always re-
applies the rung below, so ``r_{i+1}`` is never ``r2(r2(x))`` for a searchable ``x`` (verified at
height 3 AND 4 by the in-memory certificate before committing).

Floor ``{concat_h, concat_v, translate}`` -> ``pair`` -> ``stack`` -> top.

- ``r1 = pair``: ``concat_h(g, translate(g, 1, 0))`` -- a horizontal pair, one copy row-shifted
  (asymmetric, so no flip/symmetry shortcut).
- ``r2 = stack``: ``concat_v(r1, r1)`` -- stack two ``pair``s vertically (a new axis).
- ``top``: ``concat_h(r2, r2)`` -- widen again, back on the horizontal axis.

Clean against all four families for the same structural reasons as al15 (asymmetric target; spatial,
not colour; rigid concat/translate floor) -- and against telescoping specifically because the layout
op wraps the rung below rather than acting on arbitrary grids. Sandwich pinned at ``depth_limit=2``.
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
from arc_lab.program_search.substrate.types import GRID, INT
from arc_lab.taskgen.ladders import LadderTestbed, RungTasks, TopTasks

_G = Param(0, GRID)
_FULL = DemonstrationKind.FULL_SOLUTION
_ONE = Const(1, INT)
_ZERO = Const(0, INT)


def _a(name: str, *args: Program) -> Apply:
    return Apply(name, tuple(args))


NAME = "al16-layout-nest"

FLOOR = Library(
    name="al16-L0",
    primitives=tuple(BASE_PRIMITIVES[n] for n in ("concat_h", "concat_v", "translate")),
)
#: r1 -- a horizontal pair, second copy row-shifted (asymmetric).
PAIR = _a("concat_h", _G, _a("translate", _G, _ONE, _ZERO))
#: r2 -- stack two pairs vertically (a new axis; wraps r1, so it is not a free-standing doubler).
STACK = _a("concat_v", _a("pair", _G), _a("pair", _G))
#: top -- widen the stack horizontally.
TOP = _a("concat_h", _a("stack", Input()), _a("stack", Input()))

_RUNGS = (("pair", PAIR), ("stack", STACK))
REFERENCE_BUDGET = Budget(depth_limit=2, max_arity=2, max_pool=400)


def testbed() -> LadderTestbed:
    return LadderTestbed(
        floor=FLOOR,
        rungs=tuple(
            RungTasks(
                name=n,
                template=t,
                train_args=((), ()),
                heldout_args=((),),
                rows=2,
                cols=3,
                palette=(1, 2, 3, 4),
            )
            for n, t in _RUNGS
        ),
        top=TopTasks(
            solutions=(TOP,), heldout_solutions=(TOP,), rows=2, cols=3, palette=(1, 2, 3, 4)
        ),
        note="al16-layout-nest: nested-layout chain; certified non-collapsing at heights 3 and 4.",
    )


def build() -> LadderSpec:
    reference_config = Config(
        library=FLOOR,
        search_engine=BottomUpSearchEngine(
            constant_sources=("finite-enumerate",),
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=REFERENCE_BUDGET,
        learn=LearnSpec(learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()), iterations=5),
    )
    return spec_from_testbed(
        NAME,
        reference_config=reference_config,
        rungs=tuple((n, t, _FULL) for n, t in _RUNGS),
        top_solutions=(TOP,),
    )
