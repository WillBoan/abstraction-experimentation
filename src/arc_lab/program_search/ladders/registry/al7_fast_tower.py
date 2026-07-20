"""``al7-fast-tower``: height 6 with every jump at depth 2 -- the tall-AND-cheap ladder.

The batch had no ladder that was both tall and quick, so "does the loop climb six rungs?" could not
be iterated on. This fixes that. The trick is that al3's Floor costs 973k candidates at
``depth_limit=4`` but only **61** at ``depth_limit=2`` -- so a tower whose every jump is depth 2
runs on the same layout floor for a rounding error.

Each rung doubles one dimension by stacking the rung below against itself, alternating axes. From a
2x3 seed the widths/heights run 2x6 -> 4x6 -> 4x12 -> 8x12 -> 8x24 -> 16x24, inside the ARC 30 cap.
Grid growth is what keeps the tower non-collapsing (a size-preserving tower on a finite grid must
eventually cycle) -- and it is also what caps height at roughly 6.
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
from arc_lab.program_search.substrate.program import Apply, Input, Param, Program
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import GRID
from arc_lab.taskgen.ladders import LadderTestbed, RungTasks, TopTasks

_G = Param(0, GRID)
_FULL = DemonstrationKind.FULL_SOLUTION


def _a(name: str, *args: Program) -> Apply:
    return Apply(name, tuple(args))


NAME = "al7-fast-tower"

FLOOR = Library(
    name="al7-L0",
    primitives=tuple(BASE_PRIMITIVES[n] for n in ("concat_h", "concat_v", "flip_h", "flip_v")),
)
#: r1 -- mirror against a horizontal flip (the only rung that touches D4).
MIRROR = _a("concat_h", _G, _a("flip_h", _G))
#: r2..r5 -- each doubles a dimension by stacking the rung below against itself.
STACK2 = _a("concat_v", _a("mirror", _G), _a("mirror", _G))
WIDE4 = _a("concat_h", _a("stack2", _G), _a("stack2", _G))
TALL4 = _a("concat_v", _a("wide4", _G), _a("wide4", _G))
WIDE8 = _a("concat_h", _a("tall4", _G), _a("tall4", _G))
TOP = _a("concat_v", _a("wide8", Input()), _a("wide8", Input()))

_RUNGS = (
    ("mirror", MIRROR),
    ("stack2", STACK2),
    ("wide4", WIDE4),
    ("tall4", TALL4),
    ("wide8", WIDE8),
)
REFERENCE_BUDGET = Budget(depth_limit=2, max_arity=2, max_pool=400)


def testbed() -> LadderTestbed:
    return LadderTestbed(
        floor=FLOOR,
        rungs=tuple(
            RungTasks(name=n, template=t, train_args=((), ()), heldout_args=((),), rows=2, cols=3)
            for n, t in _RUNGS
        ),
        top=TopTasks(solutions=(TOP,), heldout_solutions=(TOP,), rows=2, cols=3),
        note="al7-fast-tower: layout floor, height 6, every jump depth 2, no constant sources.",
    )


def build() -> LadderSpec:
    reference_config = Config(
        library=FLOOR,
        search_engine=BottomUpSearchEngine(
            constant_sources=(),
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=REFERENCE_BUDGET,
        learn=LearnSpec(
            learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()),
            iterations=8,  # height 6 needs >= 6 climbing wakes + termination headroom
        ),
    )
    return spec_from_testbed(
        NAME,
        reference_config=reference_config,
        rungs=tuple((n, t, _FULL) for n, t in _RUNGS),
        top_solutions=(TOP,),
    )
