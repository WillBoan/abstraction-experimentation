"""``al19-fanin-recolor``: fan-in > 1 where the recombined rungs differ by *colour*, not geometry.

The colour sibling of al18: instead of stacking ``pair`` against its rotation, it stacks ``pair``
against a *recoloured* ``pair`` -- so the fan-in recombines a geometric rung with a colour-remapped
one. Shares ``r1``/``r2`` with al20 but recombines them (``concat_v(pair, recol)``) instead of
telescoping, which makes the two a clean fan-in-vs-telescope contrast on identical rungs.

Floor ``{concat_h, concat_v, translate, map_color}`` -> ``pair`` -> ``recol`` -> top.

- ``r1 = pair``: ``concat_h(g, translate(g, 1, 0))``.
- ``r2 = recol``: ``map_color(pair, 1, 7)`` (references ``pair``; shape-preserving, so it recombines).
- ``top``: ``concat_v(pair, recol)`` -- **fan-in 2**.

``map_color`` appears as one *component*, never the whole competence -- the Family-B collapse (al5/
al6/al8) was recolour-*only* ladders, which have no compositional depth; here the geometry carries
the depth and the recolour is a sibling rung. Sandwich at ``depth_limit=2``.
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


NAME = "al19-fanin-recolor"

FLOOR = Library(
    name="al19-L0",
    primitives=tuple(BASE_PRIMITIVES[n] for n in ("concat_h", "concat_v", "translate", "map_color")),
)
PAIR = _a("concat_h", _G, _a("translate", _G, _ONE, _ZERO))
RECOL = _a("map_color", _a("pair", _G), _ONE, Const(7, COLOR))
TOP = _a("concat_v", _a("pair", Input()), _a("recol", Input()))

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
        note="al19-fanin-recolor: fan-in-2 over a geometric and a recoloured rung; certified clean.",
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
