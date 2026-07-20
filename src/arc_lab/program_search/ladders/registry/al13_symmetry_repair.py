"""``al13-symmetry-repair``: symmetry stops being a transformation and becomes an *inference rule*.

L0 {overlay, flip_h, flip_v, transpose} -> sym_h -> sym_both -> top. ``overlay(c, a, b)`` merges two
grids treating ``c`` as transparent, so ``overlay(c, g, flip_h g)`` fills whatever the horizontal
mirror can supply -- ie it **repairs** a grid from its own symmetry rather than merely transforming
it. That is a genuinely different kind of abstraction from anything else in the batch, where every
rung is a mapping; here a rung reconstructs missing data.

``overlay`` is variadic, so ``max_arity`` must admit (colour + two grids).

**Partly fixed, but a residual skip is STRUCTURAL (2026-07-20).** The original seeds were dense
stride grids, so ``sym_both`` was a no-op (H-repair filled everything) and the top was Floor-
reachable -- now fixed by ``symmetry_repair_seeds`` (holed grids needing both axes), which removed
that raw collapse (``raw_solved`` true -> false). But the certificate still finds a level-1 skip, and
it is unavoidable within this Floor: a both-H-and-V-symmetric target is necessarily rot180-symmetric,
and a balanced depth-3 overlay tree ``overlay(overlay(g, flip_h g), overlay(flip_v g, rot180 g))``
unions all four D4 mirrors -- which reconstructs the target exactly when ``sym_both`` (depth 4) can,
one depth cheaper. The Floor ``{overlay, flip_h, flip_v}`` is "repair-complete" a rung below the
intended one, so ``sym_both`` can never be made necessary here. A clean version needs a
single-direction repair primitive (not a mirror-union) or a Floor without both flips -- a
reconception. Left in the registry with the improved seeds; do not expect ``admitted`` yet.
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
from arc_lab.program_search.substrate.types import COLOR, GRID
from arc_lab.taskgen.ladders import LadderTestbed, RungTasks, TopTasks

_G = Param(0, GRID)
_FULL = DemonstrationKind.FULL_SOLUTION


def _a(name: str, *args: Program) -> Apply:
    return Apply(name, tuple(args))


NAME = "al13-symmetry-repair"

FLOOR = Library(
    name="al13-L0",
    primitives=tuple(BASE_PRIMITIVES[n] for n in ("overlay", "flip_h", "flip_v", "transpose")),
)
#: r1 -- repair against the horizontal mirror; the free param is the transparent colour (d=2).
SYM_H = _a("overlay", Param(1, COLOR), _G, _a("flip_h", _G))
#: r2 -- repair on both axes (d=3), calling r1 twice.
SYM_BOTH = _a(
    "overlay",
    Param(1, COLOR),
    _a("sym_h", _G, Param(1, COLOR)),
    _a("flip_v", _a("sym_h", _G, Param(1, COLOR))),
)
TOP = _a("transpose", _a("sym_both", Input(), Const(0, COLOR)))

_RUNGS = (("sym_h", SYM_H), ("sym_both", SYM_BOTH))
REFERENCE_BUDGET = Budget(depth_limit=3, max_arity=3, max_pool=1000)


def testbed() -> LadderTestbed:
    """Seeds are ``symmetry-repair`` holed grids (``taskgen.ladders.symmetry_repair_seeds``): a
    corner cell needs BOTH mirrors to reconstruct, so ``sym_h`` alone leaves it blank and ``sym_both``
    is genuinely necessary. Dense stride seeds made ``sym_both`` a no-op and the rung skippable."""
    return LadderTestbed(
        floor=FLOOR,
        rungs=(
            RungTasks(
                name="sym_h",
                template=SYM_H,
                train_args=((0,), (0,)),
                heldout_args=((0,),),
                rows=3,
                cols=4,
                palette=(0, 1, 2, 3, 4, 5),
                seed_mode="symmetry-repair",
            ),
            RungTasks(
                name="sym_both",
                template=SYM_BOTH,
                train_args=((0,), (0,)),
                heldout_args=((0,),),
                rows=3,
                cols=4,
                palette=(0, 1, 2, 3, 4, 5),
                seed_mode="symmetry-repair",
            ),
        ),
        top=TopTasks(
            solutions=(TOP,),
            heldout_solutions=(TOP,),
            rows=3,
            cols=4,
            palette=(0, 1, 2, 3, 4, 5),
            seed_mode="symmetry-repair",
        ),
        note="al13-symmetry-repair: overlay-based symmetry repair; a rung that INFERS missing cells.",
    )


def build() -> LadderSpec:
    reference_config = Config(
        library=FLOOR,
        search_engine=BottomUpSearchEngine(
            constant_sources=("finite-enumerate",),  # the transparent colour is a free param
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
