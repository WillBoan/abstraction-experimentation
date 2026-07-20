"""``al12-unlearnable`` (control): a rung with ONE demonstrating task -- a climb designed to fail.

No experiment has ever produced a failed climb, so every success in the batch is uncalibrated: we do
not know what failure looks like in the trace, the certificate, or the rung-recovery table. This
control manufactures one. ``AntiunifyPairs`` generalises by antiunifying *pairs* of solutions, so a
rung demonstrated by a single task has nothing to pair with and cannot be minted, however cheap it is
to solve.

**Expected to FAIL its lint** (``min-2-demos``) and to climb no further than r1's own tasks. Its
value is the shape of the failure, which is the reference against which every real climb is read.
"""

from __future__ import annotations

from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.model.learn_spec import LearnSpec
from arc_lab.program_search.ladders.registry import al2_rot90 as al2
from arc_lab.program_search.ladders.registry._common import spec_from_testbed
from arc_lab.program_search.ladders.spec import DemonstrationKind, LadderSpec
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.taskgen.ladders import LadderTestbed, RungTasks, TopTasks

NAME = "al12-unlearnable"


def testbed() -> LadderTestbed:
    """ONE train demo for rot90 -- the deliberate violation."""
    return LadderTestbed(
        floor=al2.FLOOR,
        rungs=(
            RungTasks(
                name="rot90",
                template=al2.ROT90,
                train_args=((),),  # a single demonstrating task: nothing to antiunify against
                heldout_args=((),),
                rows=2,
                cols=3,
            ),
        ),
        top=TopTasks(solutions=(al2.TOP,), heldout_solutions=(al2.TOP,), rows=2, cols=3),
        note="al12-unlearnable (control): rot90 has ONE demo, so AntiunifyPairs cannot mint it.",
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
        budget=al2.REFERENCE_BUDGET,
        learn=LearnSpec(learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()), iterations=4),
    )
    return spec_from_testbed(
        NAME,
        reference_config=reference_config,
        rungs=(("rot90", al2.ROT90, DemonstrationKind.FULL_SOLUTION),),
        top_solutions=(al2.TOP,),
    )
