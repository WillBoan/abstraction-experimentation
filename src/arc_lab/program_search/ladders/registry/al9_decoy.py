"""``al9-decoy`` (control): al7's spine plus a learnable competence that the ladder never uses.

The batch's ladders all assume every mintable abstraction is on the spine. Real corpora are not like
that. This control adds two **distractor** tasks -- solved by ``concat_v(g, flip_v g)``, perfectly
learnable at the Floor and perfectly useless for the climb -- and asks what the loop does with them:
pay only the vocabulary tax, or derail (mint the distractor first, displace a real rung, stall)?

Only the corpus differs from al7; the spine, floor, budget and depths are identical, so any
difference in the climb is attributable to the distractor alone.
"""

from __future__ import annotations

from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.model.learn_spec import LearnSpec
from arc_lab.program_search.ladders.registry import al7_fast_tower as al7
from arc_lab.program_search.ladders.registry._common import spec_from_testbed
from arc_lab.program_search.ladders.spec import DemonstrationKind, LadderSpec
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.substrate.program import Apply, Param
from arc_lab.program_search.substrate.types import GRID
from arc_lab.taskgen.ladders import LadderTestbed, RungTasks, TopTasks

NAME = "al9-decoy"
_G = Param(0, GRID)
#: Off-spine and floor-expressible: learnable, and never useful above.
DECOY = Apply("concat_v", (_G, Apply("flip_v", (_G,))))
REFERENCE_BUDGET = Budget(depth_limit=2, max_arity=2, max_pool=400)


def testbed() -> LadderTestbed:
    return LadderTestbed(
        floor=al7.FLOOR,
        rungs=tuple(
            RungTasks(name=n, template=t, train_args=((), ()), heldout_args=((),), rows=2, cols=3)
            for n, t in al7._RUNGS
        ),
        top=TopTasks(solutions=(al7.TOP,), heldout_solutions=(al7.TOP,), rows=2, cols=3),
        distractors=(
            RungTasks(
                name="decoy", template=DECOY, train_args=((), ()), heldout_args=(), rows=2, cols=3
            ),
        ),
        note="al9-decoy (control): al7 + a learnable-but-unused competence in the corpus.",
    )


def build() -> LadderSpec:
    reference_config = Config(
        library=al7.FLOOR,
        search_engine=BottomUpSearchEngine(
            constant_sources=(),
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=REFERENCE_BUDGET,
        learn=LearnSpec(learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()), iterations=8),
    )
    return spec_from_testbed(
        NAME,
        reference_config=reference_config,
        rungs=tuple((n, t, DemonstrationKind.FULL_SOLUTION) for n, t in al7._RUNGS),
        top_solutions=(al7.TOP,),
    )
