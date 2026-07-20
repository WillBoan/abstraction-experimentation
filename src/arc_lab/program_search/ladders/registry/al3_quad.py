"""``al3-quad-symmetrize``: the param-free, binary-primitive cost arm -- height 4, jumps [4,3,3].

L0 {concat_h, concat_v, flip_h, flip_v} -> quad -> band -> tower -> top. Nothing here takes a
non-grid argument, so there are **no constant sources at all**: the entire search cost is
composition over grids. That makes it the clean contrast against al5/al6, where enumerated COLOR
constants dominate. What it costs instead is *binary* primitives -- ``concat_h``/``concat_v`` compose
pairwise, so candidate counts grow quadratically in pool size rather than linearly.

Grids double each level, so seeds must stay small: a 2x3 seed grows 4x6 -> 4x12 -> 8x12 -> 16x12,
inside the ARC 30 cap with room; a larger seed would overflow at the top.
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
from arc_lab.program_search.substrate.program import Apply, Input, Param
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import GRID
from arc_lab.taskgen.ladders import LadderTestbed, RungTasks, TopTasks

NAME = "al3-quad-symmetrize"
_G = Param(0, GRID)

FLOOR = Library(
    name="al3-L0",
    primitives=tuple(BASE_PRIMITIVES[n] for n in ("concat_h", "concat_v", "flip_h", "flip_v")),
)
#: r1 -- the 4-fold symmetric completion, written out over the Floor (d=4).
QUAD = Apply(
    "concat_v",
    (
        Apply("concat_h", (_G, Apply("flip_h", (_G,)))),
        Apply("flip_v", (Apply("concat_h", (_G, Apply("flip_h", (_G,)))),)),
    ),
)
#: r2 -- mirror the quad horizontally (d=3 over L_1).
BAND = Apply("concat_h", (Apply("quad", (_G,)), Apply("flip_h", (Apply("quad", (_G,)),))))
#: r3 -- mirror the band vertically (d=3 over L_2).
TOWER = Apply("concat_v", (Apply("band", (_G,)), Apply("flip_v", (Apply("band", (_G,)),))))
#: Top -- one more vertical mirroring. Nests ``tower`` two levels down so the top-skip check bites.
TOP = Apply(
    "concat_v", (Apply("tower", (Input(),)), Apply("flip_v", (Apply("tower", (Input(),)),)))
)

REFERENCE_BUDGET = Budget(depth_limit=4, max_arity=2, max_pool=2000)


def testbed() -> LadderTestbed:
    """2 demos + 1 heldout per rung, 1 top + 1 heldout. Param-free throughout, so demo variety comes
    from distinct seeds; 2x3 seeds are asymmetric on both axes (no flip/identity shortcut)."""
    return LadderTestbed(
        floor=FLOOR,
        rungs=tuple(
            RungTasks(
                name=name,
                template=template,
                train_args=((), ()),
                heldout_args=((),),
                rows=2,
                cols=3,
            )
            for name, template in (("quad", QUAD), ("band", BAND), ("tower", TOWER))
        ),
        top=TopTasks(solutions=(TOP,), heldout_solutions=(TOP,), rows=2, cols=3),
        note=(
            "al3-quad-symmetrize: L0 {concat_h, concat_v, flip_h, flip_v} -> quad -> band -> "
            "tower -> top. Param-free, no constant sources; the binary-primitive cost arm."
        ),
    )


def build() -> LadderSpec:
    """Construct the ``al3-quad-symmetrize`` LadderSpec from the committed testbed."""
    reference_config = Config(
        library=FLOOR,
        search_engine=BottomUpSearchEngine(
            constant_sources=(),  # no primitive here takes a non-grid argument
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=REFERENCE_BUDGET,
        learn=LearnSpec(
            learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()),
            iterations=6,  # height 4 needs >= 4 climbing wakes + termination headroom
        ),
    )
    return spec_from_testbed(
        NAME,
        reference_config=reference_config,
        rungs=(
            ("quad", QUAD, DemonstrationKind.FULL_SOLUTION),
            ("band", BAND, DemonstrationKind.FULL_SOLUTION),
            ("tower", TOWER, DemonstrationKind.FULL_SOLUTION),
        ),
        top_solutions=(TOP,),
    )
