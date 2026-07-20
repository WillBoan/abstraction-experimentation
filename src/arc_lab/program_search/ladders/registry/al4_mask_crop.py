"""``al4-mask-crop``: the learned-``Mask``-intermediate arm -- height 4, jumps [3,4,3], d_raw 12.

L0 (mask algebra + colour perceivers, with ``nonbg_mask``/``crop_to_content``/``bbox_mask``
**withheld**) -> nonbg_mask -> flatten_content -> stamp -> top. Because the withheld primitives are
shipped, every rung has a ready-made gen/full contrast.

**Why this ladder is the odd one out.** r1's target, ``nonbg_mask``, is ``GRID -> MASK`` -- so no
grid-to-grid task can have it as a whole solution, and it can only ever be demonstrated as a
*fragment*. Its demonstrating tasks are therefore solved by a grid-to-grid wrapper that contains it
(``crop_to_mask(g, nonbg_mask g)``, ie ``crop_to_content``), the rung is marked
``FRAGMENT_IDENTICAL``, and the proposer is ``FrequentSubtree`` rather than ``AntiunifyPairs`` --
which is what the lint's proposer-compatibility check demands, and what makes this the only ladder
in the batch not using the default proposer (a confound to remember when comparing across ladders).

This is the same wall the quantity-typed rungs of `counting-histogram` hit, arriving early: any rung
whose type is not the task's goal type needs fragment machinery, not antiunification.
"""

from __future__ import annotations

from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.model.learn_spec import LearnSpec
from arc_lab.program_search.ladders.registry._common import spec_from_testbed
from arc_lab.program_search.ladders.spec import DemonstrationKind, LadderSpec
from arc_lab.program_search.learn.antiunify import FrequentSubtree
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Apply, Const, Input, Param
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import COLOR, GRID
from arc_lab.taskgen.ladders import LadderTestbed, RungTasks, TopTasks

NAME = "al4-mask-crop"
_G = Param(0, GRID)

FLOOR = Library(
    name="al4-L0",
    primitives=tuple(
        BASE_PRIMITIVES[n]
        for n in (
            "mask_by_color",
            "most_common_color",
            "least_common_color",
            "mask_complement",
            "mask_union",
            "mask_intersect",
            "crop_to_mask",
            "paint_through_mask",
            "flip_h",
        )
    ),
)
#: r1 TARGET -- the mask of everything that is not background (d=3). GRID -> MASK.
NONBG_MASK = Apply(
    "mask_complement",
    (Apply("mask_by_color", (_G, Apply("most_common_color", (_G,)))),),
)
#: r1 DEMO template -- a grid-to-grid wrapper CONTAINING the target, since the target itself can
#: never be a whole solution. This is `crop_to_content`, one of the withheld primitives.
CROP_TO_CONTENT = Apply("crop_to_mask", (_G, Apply("nonbg_mask", (_G,))))
#: r2 -- crop to content, then flatten every non-background cell to one colour (d=4).
FLATTEN_CONTENT = Apply(
    "paint_through_mask",
    (
        Apply("crop_to_mask", (_G, Apply("nonbg_mask", (_G,)))),
        Apply("nonbg_mask", (Apply("crop_to_mask", (_G, Apply("nonbg_mask", (_G,)))),)),
        Param(1, COLOR),
    ),
)
#: r3 -- mirror the flattened crop and stamp a second colour through a colour-selected mask (d=3).
STAMP = Apply(
    "paint_through_mask",
    (
        Apply("flip_h", (Apply("flatten_content", (_G, Param(1, COLOR))),)),
        Apply(
            "mask_by_color",
            (Apply("flatten_content", (_G, Param(1, COLOR))), Param(1, COLOR)),
        ),
        Param(2, COLOR),
    ),
)
#: Top -- nests `stamp` two levels down so the top-skip check bites.
TOP = Apply(
    "flip_h",
    (Apply("flip_h", (Apply("stamp", (Input(), Const(3, COLOR), Const(5, COLOR))),)),),
)

REFERENCE_BUDGET = Budget(depth_limit=4, max_arity=3, max_pool=2000)


def testbed() -> LadderTestbed:
    """2 demos + 1 heldout per rung. r1's tasks are generated from the WRAPPER (``crop_to_content``),
    not from the target -- see the module docstring. Seeds carry a clear majority background with
    off-centre content and varying margins, so a fixed crop cannot coincide."""
    return LadderTestbed(
        floor=FLOOR,
        rungs=(
            RungTasks(
                name="nonbg_mask",
                template=CROP_TO_CONTENT,  # demos are solved by the wrapper ...
                target_template=NONBG_MASK,  # ... but THIS is what sleep must mint
                train_args=((), ()),
                heldout_args=((),),
                rows=4,
                cols=5,
                palette=(1, 2, 3),
                background=0,
            ),
            RungTasks(
                name="flatten_content",
                template=FLATTEN_CONTENT,
                train_args=((3,), (7,)),
                heldout_args=((5,),),
                rows=4,
                cols=5,
                palette=(1, 2, 3),
                background=0,
            ),
            RungTasks(
                name="stamp",
                template=STAMP,
                train_args=((3, 8), (7, 9)),
                heldout_args=((5, 6),),
                rows=4,
                cols=5,
                palette=(1, 2, 3),
                background=0,
            ),
        ),
        top=TopTasks(
            solutions=(TOP,),
            heldout_solutions=(TOP,),
            rows=4,
            cols=5,
            palette=(1, 2, 3),
            background=0,
        ),
        note=(
            "al4-mask-crop: mask algebra floor (nonbg_mask/crop_to_content/bbox_mask withheld) -> "
            "nonbg_mask -> flatten_content -> stamp -> top. The learned-Mask-intermediate arm; r1 "
            "is a FRAGMENT rung (GRID->MASK), demonstrated via a crop_to_content wrapper."
        ),
    )


def build() -> LadderSpec:
    """Construct the ``al4-mask-crop`` LadderSpec from the committed testbed."""
    reference_config = Config(
        library=FLOOR,
        search_engine=BottomUpSearchEngine(
            constant_sources=("finite-enumerate",),
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=REFERENCE_BUDGET,
        learn=LearnSpec(
            # NOT AntiunifyPairs: r1 is demonstrated as a fragment, which antiunification of whole
            # solutions cannot reach. The lint's proposer-compatibility check enforces this.
            learn_engine=GreedyMDLLearnEngine(proposer=FrequentSubtree()),
            iterations=6,
        ),
    )
    return spec_from_testbed(
        NAME,
        reference_config=reference_config,
        rungs=(
            ("nonbg_mask", NONBG_MASK, DemonstrationKind.FRAGMENT_IDENTICAL),
            ("flatten_content", FLATTEN_CONTENT, DemonstrationKind.FULL_SOLUTION),
            ("stamp", STAMP, DemonstrationKind.FULL_SOLUTION),
        ),
        top_solutions=(TOP,),
    )
