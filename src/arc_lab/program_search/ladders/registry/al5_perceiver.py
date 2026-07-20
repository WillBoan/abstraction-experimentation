"""``al5-perceiver-chain``: the constant-heavy, free-param arm -- height 4, jumps [3,3,3].

L0 {map_color, most_common_color, least_common_color, flip_h, flip_v} -> swap_extremes ->
swap_mirror -> swap_stack -> top. Free parameters grow 0 -> 1 -> 2 up the ladder, and ``map_color``
takes two COLOR arguments drawn from ``finite-enumerate``, so this is where the vocabulary tax
lands: AL1 measured a per-application factor of ~100 from exactly that pairing. al3 is the
zero-constant contrast; :mod:`al6_mirror_tall` is the same floor one rung taller (the height axis).

``swap_extremes`` is NOT a clean swap -- its first ``map_color`` rewrites the background before the
second recolour reads it, so the two recolours interact. That is fine (a task is whatever its
program computes) but it is why the generator evaluates the template rather than reimplementing it.
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

NAME = "al5-perceiver-chain"
_G = Param(0, GRID)

FLOOR = Library(
    name="al5-L0",
    primitives=tuple(
        BASE_PRIMITIVES[n]
        for n in ("map_color", "most_common_color", "least_common_color", "flip_h", "flip_v")
    ),
)
#: r1 -- two chained perceive-driven recolours; param-free (d=3).
SWAP_EXTREMES = Apply(
    "map_color",
    (
        Apply(
            "map_color",
            (
                _G,
                Apply("most_common_color", (_G,)),
                Apply("least_common_color", (_G,)),
            ),
        ),
        Apply("least_common_color", (_G,)),
        Apply("most_common_color", (_G,)),
    ),
)
#: r2 -- mirror the normalized grid, then recolour its background to a free colour (d=3).
SWAP_MIRROR = Apply(
    "map_color",
    (
        Apply("flip_h", (Apply("swap_extremes", (_G,)),)),
        Apply("most_common_color", (_G,)),
        Param(1, COLOR),
    ),
)
#: r3 -- and again on the other axis, reading the perceiver through a flip (d=3).
SWAP_STACK = Apply(
    "map_color",
    (
        Apply("flip_v", (Apply("swap_mirror", (_G, Param(1, COLOR))),)),
        Apply("most_common_color", (Apply("flip_h", (_G,)),)),
        Param(2, COLOR),
    ),
)
#: Top -- one more mirroring over L_3.
TOP = Apply("flip_h", (Apply("swap_stack", (Input(), Const(2, COLOR), Const(6, COLOR))),))

REFERENCE_BUDGET = Budget(depth_limit=3, max_arity=3, max_pool=1500)


def testbed() -> LadderTestbed:
    """2 demos + 1 heldout per rung. Free params are fixed within a task and varied across tasks
    (the design doc's variation plan); seeds vary the perceived colours per example so no literal
    ``map_color(g, k1, k2)`` can coincide -- the E11 trap, which this floor is squarely exposed to."""
    return LadderTestbed(
        floor=FLOOR,
        rungs=(
            RungTasks(
                name="swap_extremes",
                template=SWAP_EXTREMES,
                train_args=((), ()),
                heldout_args=((),),
                palette=(1, 2, 3, 4),
            ),
            RungTasks(
                name="swap_mirror",
                template=SWAP_MIRROR,
                train_args=((3,), (7,)),
                heldout_args=((5,),),
                palette=(1, 2, 3, 4),
            ),
            RungTasks(
                name="swap_stack",
                template=SWAP_STACK,
                train_args=((3, 8), (7, 9)),
                heldout_args=((5, 6),),
                palette=(1, 2, 3, 4),
            ),
        ),
        top=TopTasks(solutions=(TOP,), heldout_solutions=(TOP,), palette=(1, 2, 3, 4)),
        note=(
            "al5-perceiver-chain: L0 {map_color, most_common_color, least_common_color, flip_h, "
            "flip_v} -> swap_extremes -> swap_mirror -> swap_stack -> top. The constant-heavy arm; "
            "free params 0 -> 1 -> 2 up the ladder."
        ),
    )


def build() -> LadderSpec:
    """Construct the ``al5-perceiver-chain`` LadderSpec from the committed testbed."""
    reference_config = Config(
        library=FLOOR,
        search_engine=BottomUpSearchEngine(
            constant_sources=("finite-enumerate",),  # map_color needs COLOR constants
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=REFERENCE_BUDGET,
        learn=LearnSpec(
            learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()),
            iterations=6,
        ),
    )
    return spec_from_testbed(
        NAME,
        reference_config=reference_config,
        rungs=(
            ("swap_extremes", SWAP_EXTREMES, DemonstrationKind.FULL_SOLUTION),
            ("swap_mirror", SWAP_MIRROR, DemonstrationKind.FULL_SOLUTION),
            ("swap_stack", SWAP_STACK, DemonstrationKind.FULL_SOLUTION),
        ),
        top_solutions=(TOP,),
    )
