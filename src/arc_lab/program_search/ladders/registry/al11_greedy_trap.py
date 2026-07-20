"""``al11-greedy-trap`` (control): a distractor that is MORE compressive than the real rung.

``GreedyMDL`` mints whatever compresses the corpus most. This control puts a bigger shared template
in front of it: the distractor ``concat_h(concat_v(g, g), concat_v(g, g))`` is a 5-node motif shared
across its demos, against al7's r1 ``concat_h(g, flip_h g)`` at 4 nodes. If governance is purely
size-greedy it should prefer the distractor at the first sleep -- and the question is whether the
climb then recovers, stalls, or mints the real rung a wake later than it should.

Distinct from al9-decoy: there the distractor is merely *available*, here it is deliberately made
*more attractive* than the rung it competes with.
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

NAME = "al11-greedy-trap"
_G = Param(0, GRID)
#: 5 nodes vs r1's 4 -- deliberately the better MDL bargain, and useless for the climb.
TRAP = Apply(
    "concat_h",
    (Apply("concat_v", (_G, _G)), Apply("concat_v", (_G, _G))),
)
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
                name="trap", template=TRAP, train_args=((), (), ()), heldout_args=(), rows=2, cols=3
            ),
        ),
        note="al11-greedy-trap (control): al7 + a distractor that outcompetes r1 on MDL.",
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
