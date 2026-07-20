"""``al6-mirror-tall``: the tallest ladder in the batch -- height 5, jumps [2,3,3,3].

Same floor as :mod:`al5_perceiver` plus nothing: al5 is height 4, al6 is height 5, so the pair is
the batch's **height axis** with the floor held constant. r1 is AL1's own ``rot180``, so this is a
genuine upward extension of ladder #1 rather than a separate design -- AL1 becomes its shallow
control.

Note r1 is d=2 while every rung above is d=3. That is fine, and the reason is worth recording: the
double-jump check is about **call-site nesting**, not depth uniformity. Skipping ``r_i`` is forbidden
iff ``(nesting of the r_i call site inside r_{i+1}) + d_i > depth_limit``; ``norm_mirror`` calls
``rot180`` at nesting 2, so 2 + 2 = 4 > 3 and the rung is unskippable despite being shallow. An
earlier draft called it at nesting 1 (3, not > 3) and the rung was free to skip.
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
from arc_lab.program_search.substrate.program import Apply, Const, Input, Param
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import COLOR, GRID
from arc_lab.taskgen.ladders import LadderTestbed, RungTasks, TopTasks

NAME = "al6-mirror-tall"
_G = Param(0, GRID)

#: AL1's floor + both perceivers. The perceivers are what let rungs gain depth without gaining free
#: params -- an all-``map_color`` tower would need 6 COLOR params by r4 (10^6 instantiations).
FLOOR = Library(
    name="al6-L0",
    primitives=tuple(
        BASE_PRIMITIVES[n]
        for n in ("flip_h", "flip_v", "map_color", "most_common_color", "least_common_color")
    ),
)
#: r1 -- AL1's rung, unchanged (d=2). Note `rot180` is deliberately NOT on the floor: if it were,
#: this rung would collapse to depth 1 and stop being a rung at all.
ROT180 = Apply("flip_h", (Apply("flip_v", (_G,)),))
#: r2 -- calls rot180 at nesting 2 (see module docstring) and recolours to a free colour (d=3).
NORM_MIRROR = Apply(
    "map_color",
    (
        Apply("flip_h", (Apply("rot180", (_G,)),)),
        Apply("most_common_color", (_G,)),
        Param(1, COLOR),
    ),
)
#: r3 (d=3).
NORM_STACK = Apply(
    "map_color",
    (
        Apply("flip_v", (Apply("norm_mirror", (_G, Param(1, COLOR))),)),
        Apply("least_common_color", (Apply("flip_h", (_G,)),)),
        Param(2, COLOR),
    ),
)
#: r4 (d=3).
NORM_QUAD = Apply(
    "map_color",
    (
        Apply("flip_h", (Apply("norm_stack", (_G, Param(1, COLOR), Param(2, COLOR))),)),
        Apply("most_common_color", (Apply("flip_v", (_G,)),)),
        Param(3, COLOR),
    ),
)
#: Top over L_4.
TOP = Apply(
    "flip_v",
    (Apply("norm_quad", (Input(), Const(1, COLOR), Const(7, COLOR), Const(4, COLOR))),),
)

REFERENCE_BUDGET = Budget(depth_limit=3, max_arity=3, max_pool=1500)


def testbed() -> LadderTestbed:
    """2 demos + 1 heldout per rung, across five levels. Free params reach 3 at r4 -- with
    ``finite-enumerate`` that is the ladder's dominant cost, and the reason it is the one most
    likely to wall."""
    return LadderTestbed(
        floor=FLOOR,
        rungs=(
            RungTasks(
                name="rot180",
                template=ROT180,
                train_args=((), ()),
                heldout_args=((),),
                palette=(1, 2, 3, 4),
            ),
            RungTasks(
                name="norm_mirror",
                template=NORM_MIRROR,
                train_args=((3,), (7,)),
                heldout_args=((5,),),
                palette=(1, 2, 3, 4),
            ),
            RungTasks(
                name="norm_stack",
                template=NORM_STACK,
                train_args=((3, 8), (7, 9)),
                heldout_args=((5, 6),),
                palette=(1, 2, 3, 4),
            ),
            RungTasks(
                name="norm_quad",
                template=NORM_QUAD,
                train_args=((3, 8, 2), (7, 9, 6)),
                heldout_args=((5, 6, 0),),
                palette=(1, 2, 3, 4),
            ),
        ),
        top=TopTasks(solutions=(TOP,), heldout_solutions=(TOP,), palette=(1, 2, 3, 4)),
        note=(
            "al6-mirror-tall: AL1's floor + perceivers, climbed five levels "
            "(rot180 -> norm_mirror -> norm_stack -> norm_quad -> top). The height-axis partner "
            "of al5 and an upward extension of ladder #1."
        ),
    )


def build() -> LadderSpec:
    """Construct the ``al6-mirror-tall`` LadderSpec from the committed testbed."""
    reference_config = Config(
        library=FLOOR,
        search_engine=BottomUpSearchEngine(
            constant_sources=("finite-enumerate",),
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=REFERENCE_BUDGET,
        learn=LearnSpec(
            learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()),
            iterations=7,  # height 5 needs >= 5 climbing wakes + termination headroom
        ),
    )
    return spec_from_testbed(
        NAME,
        reference_config=reference_config,
        rungs=(
            ("rot180", ROT180, DemonstrationKind.FULL_SOLUTION),
            ("norm_mirror", NORM_MIRROR, DemonstrationKind.FULL_SOLUTION),
            ("norm_stack", NORM_STACK, DemonstrationKind.FULL_SOLUTION),
            ("norm_quad", NORM_QUAD, DemonstrationKind.FULL_SOLUTION),
        ),
        top_solutions=(TOP,),
    )
