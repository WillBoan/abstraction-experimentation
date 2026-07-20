"""``al10-skippable`` (control): al2's spine at a budget deep enough to make its rung SKIPPABLE.

Every other ladder enforces the sandwich strictly: the layer above must be unreachable without the
rung below. This control breaks exactly that one rule and nothing else. al2's top-skip depth is 4,
so pinning ``depth_limit=4`` (instead of 2) means the top is reachable raw -- the rung buys nothing.

**This ladder is expected to FAIL its lint** (``top-double-jump-intractable``) and to be REJECTED by
the certificate (``no_skip_paths`` false). That is the control working, not a defect. What it
measures is what rung-necessity enforcement actually buys -- settling empirically what the design
doc settled by fiat.
"""

from __future__ import annotations

from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.model.learn_spec import LearnSpec
from arc_lab.program_search.ladders.registry import al2_rot90 as al2
from arc_lab.program_search.ladders.registry._common import spec_from_testbed
from arc_lab.program_search.ladders.spec import DemonstrationKind, LadderSpec
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.taskgen.ladders import LadderTestbed, RungTasks, TopTasks

NAME = "al10-skippable"
#: depth_limit 4, not al2's 2 -- deep enough to reach the top WITHOUT rot90. The whole point.
REFERENCE_BUDGET = Budget(depth_limit=4, max_arity=2, max_pool=4000)


def testbed() -> LadderTestbed:
    return LadderTestbed(
        floor=al2.FLOOR,
        rungs=(
            RungTasks(
                name="rot90",
                template=al2.ROT90,
                train_args=((), ()),
                heldout_args=((),),
                rows=2,
                cols=3,
            ),
        ),
        top=TopTasks(solutions=(al2.TOP,), heldout_solutions=(al2.TOP,), rows=2, cols=3),
        note="al10-skippable (control): al2's corpus; the budget makes the rung unnecessary.",
    )


def build() -> LadderSpec:
    reference_config = Config(
        library=al2.FLOOR,
        search_engine=BottomUpSearchEngine(
            constant_sources=(),
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=REFERENCE_BUDGET,
        learn=LearnSpec(learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()), iterations=4),
    )
    return spec_from_testbed(
        NAME,
        reference_config=reference_config,
        rungs=(("rot90", al2.ROT90, DemonstrationKind.FULL_SOLUTION),),
        top_solutions=(al2.TOP,),
    )
