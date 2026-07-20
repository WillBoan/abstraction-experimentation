"""``al18-fanin-rotate``: the first ladder with fan-in > 1 -- a recombination DAG, not a telescope.

Every clean ladder so far (al1/al15/al16/al17) is a pure telescope: each rung references exactly one
below it. The design doc explicitly wants the recombination regime, where a rung (or the top) draws
on *several* lower rungs. This is the smallest such ladder: the top stacks ``pair`` against its own
``rot180`` -- fan-in 2.

Floor ``{concat_h, concat_v, translate, rot180}`` -> ``pair`` -> ``rot`` -> top.

- ``r1 = pair``: ``concat_h(g, translate(g, 1, 0))`` -- an asymmetric horizontal pair.
- ``r2 = rot``: ``rot180(pair)`` -- the pair rotated 180 (references ``pair``; same shape, so it
  recombines).
- ``top``: ``concat_v(pair, rot)`` -- **fan-in 2**, stacking both rungs.

Clean for the usual reasons (rigid concat/translate floor, asymmetric ``pair``, spatial not colour),
and fan-in is made to work by a *rigid* combine op (``concat``) over *size-preserving* rungs -- an
``overlay``-based recombination collapses instead (measured 2026-07-20). Sandwich at ``depth_limit=2``.
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
from arc_lab.program_search.substrate.types import GRID, INT
from arc_lab.taskgen.ladders import LadderTestbed, RungTasks, TopTasks

_G = Param(0, GRID)
_FULL = DemonstrationKind.FULL_SOLUTION
_ONE, _ZERO = Const(1, INT), Const(0, INT)


def _a(name: str, *args: Program) -> Apply:
    return Apply(name, tuple(args))


NAME = "al18-fanin-rotate"

FLOOR = Library(
    name="al18-L0",
    primitives=tuple(BASE_PRIMITIVES[n] for n in ("concat_h", "concat_v", "translate", "rot180")),
)
PAIR = _a("concat_h", _G, _a("translate", _G, _ONE, _ZERO))
ROT = _a("rot180", _a("pair", _G))
TOP = _a("concat_v", _a("pair", Input()), _a("rot", Input()))

_RUNGS = (("pair", PAIR), ("rot", ROT))
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
        note="al18-fanin-rotate: fan-in-2 recombination (pair over its rotation); certified clean.",
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
