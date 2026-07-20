"""``al8-lean-perceiver``: al5's competence with **zero free parameters** and no constant sources.

al5 measured that enumerated COLOR constants dominate its cost (63% of candidates were deduplicated
duplicates, and AL1 decomposed its b_eff almost entirely into ``map_color``'s two enumerated colour
arguments contributing x100 per application). This ladder tests that directly: the same
perceive-and-recolour competence, the same floor, the same depths -- but every colour argument is
*derived* from a perceiver instead of being a free parameter, so ``constant_sources`` is empty and
round 0 holds a single leaf instead of eleven.

If it runs in seconds where al5 takes an hour, that quantifies where the cost actually lives, and
gives the batch a fast perceiver ladder to iterate on.
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


NAME = "al8-lean-perceiver"

FLOOR = Library(
    name="al8-L0",
    primitives=tuple(
        BASE_PRIMITIVES[n]
        for n in ("map_color", "most_common_color", "least_common_color", "flip_h", "flip_v")
    ),
)
#: r1 -- two chained perceive-driven recolours (not a true swap: the first rewrites what the second
#: reads; the generator evaluates the template, so the tasks match whatever it actually computes).
SWAP_EXT = _a(
    "map_color",
    _a("map_color", _G, _a("most_common_color", _G), _a("least_common_color", _G)),
    _a("least_common_color", _G),
    _a("most_common_color", _G),
)
SWAP_MIR = _a(
    "map_color",
    _a("flip_h", _a("swap_ext", _G)),
    _a("most_common_color", _G),
    _a("least_common_color", _G),
)
SWAP_STK = _a(
    "map_color",
    _a("flip_v", _a("swap_mir", _G)),
    _a("least_common_color", _a("flip_h", _G)),
    _a("most_common_color", _a("flip_v", _G)),
)
TOP = _a("flip_h", _a("swap_stk", Input()))

_RUNGS = (("swap_ext", SWAP_EXT), ("swap_mir", SWAP_MIR), ("swap_stk", SWAP_STK))
REFERENCE_BUDGET = Budget(depth_limit=3, max_arity=3, max_pool=1500)


def testbed() -> LadderTestbed:
    return LadderTestbed(
        floor=FLOOR,
        rungs=tuple(
            RungTasks(
                name=n, template=t, train_args=((), ()), heldout_args=((),), palette=(1, 2, 3, 4)
            )
            for n, t in _RUNGS
        ),
        top=TopTasks(solutions=(TOP,), heldout_solutions=(TOP,), palette=(1, 2, 3, 4)),
        note="al8-lean-perceiver: al5's competence, param-free, constant_sources=().",
    )


def build() -> LadderSpec:
    reference_config = Config(
        library=FLOOR,
        search_engine=BottomUpSearchEngine(
            constant_sources=(),  # THE point: every colour comes from a perceiver
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
