"""``al17-shift-frame-tall``: al15's recipe at height 4 -- the height axis of the clean set.

Same non-collapsing structure as al15 (alternate a combine op with a non-composing modifier), one
rung taller: shift-stack -> frame -> shift-stack -> frame. Certified clean at height 4 in-memory
before committing (the pad between each pair of shift-stacks is what keeps the motif from
telescoping, exactly as at height 3). Sandwich pinned at ``depth_limit=2``; raw depth grows past 2
at every double jump, so all three bridging rungs are necessary.
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

_G = Param(0, GRID)
_FULL = DemonstrationKind.FULL_SOLUTION
_ONE, _ZERO = Const(1, INT), Const(0, INT)


def _a(name: str, *args: Program) -> Apply:
    return Apply(name, tuple(args))


NAME = "al17-shift-frame-tall"

FLOOR = Library(
    name="al17-L0",
    primitives=tuple(BASE_PRIMITIVES[n] for n in ("concat_v", "translate", "pad")),
)
SHIFT1 = _a("concat_v", _G, _a("translate", _G, _ZERO, _ONE))
FRAME1 = _a("pad", _a("shift1", _G), _ONE, Const(5, COLOR))
#: Written as ``shift1(frame1(g))`` -- the same grid as the inlined ``concat_v`` but depth 2 over L_2
#: (``shift1`` IS the shift-stack op), so the jump is affordable while its double jump is not.
SHIFT2 = _a("shift1", _a("frame1", _G))
TOP = _a("pad", _a("shift2", Input()), _ONE, Const(6, COLOR))

_RUNGS = (("shift1", SHIFT1), ("frame1", FRAME1), ("shift2", SHIFT2))
REFERENCE_BUDGET = Budget(depth_limit=2, max_arity=2, max_pool=400)


def testbed() -> LadderTestbed:
    return LadderTestbed(
        floor=FLOOR,
        rungs=tuple(
            RungTasks(
                name=n, template=t, train_args=((), ()), heldout_args=((),),
                rows=2, cols=3, palette=(1, 2, 3, 4),
            )
            for n, t in _RUNGS
        ),
        top=TopTasks(
            solutions=(TOP,), heldout_solutions=(TOP,), rows=2, cols=3, palette=(1, 2, 3, 4)
        ),
        note="al17-shift-frame-tall: al15's chain at height 4; certified non-collapsing.",
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
        learn=LearnSpec(learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()), iterations=6),
    )
    return spec_from_testbed(
        NAME,
        reference_config=reference_config,
        rungs=tuple((n, t, _FULL) for n, t in _RUNGS),
        top_solutions=(TOP,),
    )
