"""``al2-rot90-calibration``: the batch's calibration instrument -- height 2, raw cost measurable.

L0 {flip_h, transpose} -> r1 rot90 -> top rot180 (= rot90 o rot90). Deliberately the smallest ladder
we can build: two unary primitives and no constant sources, so the Floor's branching factor is tiny
and the raw solve (``d_raw`` = 4) is genuinely runnable -- unlike every other ladder, where raw is
intractable by construction and must be extrapolated. That makes this the one place the raw-cost
*estimator* (design doc §5.3) can be checked against a measured value.

The raw measurement is an above-window cell (``depth_limit`` 4 vs the pinned 2) -- a legitimate
calibration arm under the resolved rung-necessity decision, not a ladder defect.
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

NAME = "al2-rot90-calibration"
_G = Param(0, GRID)

FLOOR = Library(
    name="al2-L0",
    primitives=(BASE_PRIMITIVES["flip_h"], BASE_PRIMITIVES["transpose"]),
)
#: r1 -- the quarter turn, d=2 over the Floor.
ROT90 = Apply("flip_h", (Apply("transpose", (_G,)),))
#: Top -- rot180 as a self-composition of r1: d=2 over L_1, d_raw=4 over the Floor.
TOP = Apply("rot90", (Apply("rot90", (Input(),)),))

#: Pinned reference budget: rot90 affordable (2 <= 2), rot180 unreachable raw (4 > 2).
REFERENCE_BUDGET = Budget(depth_limit=2, max_arity=2, max_pool=400)
#: The above-window calibration cell: deep enough to actually SOLVE the top raw.
RAW_BUDGET = Budget(depth_limit=4, max_arity=2, max_pool=4000)


def testbed() -> LadderTestbed:
    """The corpus: 2 rot90 demos + 1 heldout, 1 top task + 1 heldout. Non-square 2x3 seeds keep the
    D4 members distinct (a square grid conflates transpose with a rotation)."""
    return LadderTestbed(
        floor=FLOOR,
        rungs=(
            RungTasks(
                name="rot90",
                template=ROT90,
                train_args=((), ()),
                heldout_args=((),),
                rows=2,
                cols=3,
            ),
        ),
        top=TopTasks(solutions=(TOP,), heldout_solutions=(TOP,), rows=2, cols=3),
        note=(
            "al2-rot90-calibration: L0 {flip_h, transpose} -> rot90 -> rot180. The calibration "
            "ladder -- raw (d_raw=4) is cheap enough to measure, anchoring the raw-cost estimator."
        ),
    )


def build() -> LadderSpec:
    """Construct the ``al2-rot90-calibration`` LadderSpec from the committed testbed."""
    reference_config = Config(
        library=FLOOR,
        search_engine=BottomUpSearchEngine(
            constant_sources=(),  # no constants: nothing on this floor takes a non-grid argument
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=REFERENCE_BUDGET,
        learn=LearnSpec(
            learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()),
            iterations=4,
        ),
    )
    return spec_from_testbed(
        NAME,
        reference_config=reference_config,
        rungs=(("rot90", ROT90, DemonstrationKind.FULL_SOLUTION),),
        top_solutions=(TOP,),
        budgets=(REFERENCE_BUDGET, RAW_BUDGET),
    )
