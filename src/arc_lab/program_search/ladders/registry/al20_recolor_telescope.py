"""``al20-recolor-telescope``: geometry + colour in a telescope -- the fan-in-1 twin of al19.

Same two rungs as al19 (``pair`` then a recoloured ``pair``), but the top *telescopes* them --
``pair`` applied to ``recol`` -- rather than recombining. The pair (al19 fan-in / al20 telescope)
isolates what the recombination structure alone changes, on identical rungs and floor.

Floor ``{concat_h, translate, map_color}`` -> ``pair`` -> ``recol`` -> top.

- ``r1 = pair``: ``concat_h(g, translate(g, 1, 0))``.
- ``r2 = recol``: ``map_color(pair, 1, 7)`` (references ``pair``).
- ``top``: ``pair(recol)`` -- pair the recoloured grid; a pure telescope (fan-in 1).

Recolour is again a *component*, not the whole competence (contrast Family B, al5/al6/al8). Sandwich
at ``depth_limit=2``; the top is written as the rung call ``pair(recol(input))`` so it is depth 2 over
L_2 while its inlined double jump exceeds the budget.
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


NAME = "al20-recolor-telescope"

FLOOR = Library(
    name="al20-L0",
    primitives=tuple(BASE_PRIMITIVES[n] for n in ("concat_h", "translate", "map_color")),
)
PAIR = _a("concat_h", _G, _a("translate", _G, _ONE, _ZERO))
RECOL = _a("map_color", _a("pair", _G), _ONE, Const(7, COLOR))
TOP = _a("pair", _a("recol", Input()))

_RUNGS = (("pair", PAIR), ("recol", RECOL))
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
        note="al20-recolor-telescope: geometry+recolour telescope (al19's fan-in-1 twin); clean.",
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
        learn=LearnSpec(learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()), iterations=5),
    )
    return spec_from_testbed(
        NAME,
        reference_config=reference_config,
        rungs=tuple((n, t, _FULL) for n, t in _RUNGS),
        top_solutions=(TOP,),
    )
