"""``al15-shift-frame``: a heterogeneous chain that provably dodges every batch collapse family.

Designed (and certified in-memory before committing) against the 2026-07-20 findings that killed
al3-al8/al13. The recipe: alternate a *combine* op (shift-stack) with a *non-composing modifier*
(frame), so no rung is a repeated motif and the chain never telescopes.

Floor ``{concat_v, translate, pad}`` -> ``shift_stack`` -> ``framed`` -> top.

- ``r1 = shift_stack``: ``concat_v(g, translate(g, 0, 1))`` -- stack ``g`` over a one-column-shifted
  copy. The ``translate`` makes it **asymmetric** (no flip fixes it), so no symmetry-union shortcut.
- ``r2 = framed``: ``pad(r1, 1, 5)`` -- a one-cell border. ``pad`` is a *different* operation from
  the stack, which is what breaks telescoping: ``r2`` is not ``r1`` applied to itself.
- ``top``: ``shift_stack`` again, over ``r2``. The ``pad`` between the two shift-stacks means
  ``top`` is NOT ``shift_stack(shift_stack(x))`` for any ``x`` -- the motif does not iterate.

Why it is clean (each family, by construction, and confirmed by the certificate):
- **A / telescoping**: every op appears with a *different* op between its uses; no self-similar
  doubler (unlike al3's ``quad``/al7's ``stack2``, where ``r_2k == r2^k``).
- **B / recolour-shallow**: builds spatial structure (stack/shift/frame), never a colour permutation
  (unlike al5/al6/al8, whose whole competence was ``map_color`` and collapsed to depth 2).
- **C / union-completeness**: the target is asymmetric (``translate``), so no variadic-``overlay``
  mirror union reconstructs it a depth early (unlike al13).
- **D / algebraic coincidence**: a rigid floor -- ``concat``/``translate``/``pad`` compose with few
  coincidental equalities (unlike al4's mask algebra).

The sandwich at ``depth_limit=2``: every jump is depth 2; raw depth is 5 and every double jump
exceeds 2, so the rungs are necessary. A modest, *tractable* ladder in the al1 mould -- deliberately
NOT the al14 dimensional-lift shape, which is structurally sound but intractable to even certify.
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
_BORDER = Const(5, COLOR)
_ONE = Const(1, INT)
_ZERO = Const(0, INT)


def _a(name: str, *args: Program) -> Apply:
    return Apply(name, tuple(args))


NAME = "al15-shift-frame"

FLOOR = Library(
    name="al15-L0",
    primitives=tuple(BASE_PRIMITIVES[n] for n in ("concat_v", "translate", "pad")),
)
#: r1 -- stack g over a one-column-shifted copy (asymmetric).
SHIFT_STACK = _a("concat_v", _G, _a("translate", _G, _ZERO, _ONE))
#: r2 -- frame r1 with a one-cell border (a DIFFERENT op, which is what breaks telescoping).
FRAMED = _a("pad", _a("shift_stack", _G), _ONE, _BORDER)
#: top -- shift-stack again, over the framed rung. Written as a call to the ``shift_stack`` rung
#: (not the inlined ``concat_v``) so it is depth 2 over L_2 -- the same grid, affordable with the
#: ladder but a depth-4 double-jump without it.
TOP = _a("shift_stack", _a("framed", Input()))

_RUNGS = (("shift_stack", SHIFT_STACK), ("framed", FRAMED))
REFERENCE_BUDGET = Budget(depth_limit=2, max_arity=2, max_pool=400)


def testbed() -> LadderTestbed:
    return LadderTestbed(
        floor=FLOOR,
        rungs=tuple(
            RungTasks(
                name=n,
                template=t,
                train_args=((), ()),  # two param-free demonstrating tasks per rung
                heldout_args=((),),
                rows=2,
                cols=3,
                palette=(1, 2, 3, 4),
            )
            for n, t in _RUNGS
        ),
        top=TopTasks(
            solutions=(TOP,), heldout_solutions=(TOP,), rows=2, cols=3, palette=(1, 2, 3, 4)
        ),
        note="al15-shift-frame: heterogeneous shift-stack/frame chain; certified non-collapsing.",
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
