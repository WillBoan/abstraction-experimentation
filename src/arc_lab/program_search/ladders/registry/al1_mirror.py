"""Abstraction Ladder #1 (``al1-mirror``): the first ladder, a height-3 synthetic anchor.

L0 {flip_h, flip_v, map_color} -> r1 rot180 -> r2 mirror_recolor -> top flip_v(mirror_recolor).
The rungs reuse E12's proven-learnable abstractions, so what is under test is the ladder machinery
(oracle chain, certificate, climb trace, amortization), not whether the abstractions mint. Verified
sandwich at depth_limit=2: jumps d=2 affordable, d_raw=4 intractable, double-jumps=3 intractable.
"""

from __future__ import annotations

from arc_lab.core.dataset import Corpus, load_testbed
from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.model.learn_spec import LearnSpec
from arc_lab.program_search.execution.model.study_spec import TargetAbstraction
from arc_lab.program_search.execution.studies import split_by_meta
from arc_lab.program_search.ladders.spec import (
    Demonstration,
    DemonstrationKind,
    LadderSpec,
    Rung,
    TopRung,
)
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.color import MAP_COLOR
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.program import Apply, Const, Input, Param
from arc_lab.program_search.substrate.types import COLOR, GRID

_ROT180 = Apply("flip_h", (Apply("flip_v", (Param(0, GRID),)),))
_MIRROR_RECOLOR = Apply(
    "map_color", (Apply("rot180", (Param(0, GRID),)), Param(1, COLOR), Param(2, COLOR))
)
#: The top reference solution over L2: map_color(mirror_recolor(g,1,2),3,4) -- a second independent
#: recolor, so it does not collapse via the D4 group law (a single-flip wrapper would).
_TOP = Apply(
    "map_color",
    (
        Apply("mirror_recolor", (Input(), Const(1, COLOR), Const(2, COLOR))),
        Const(3, COLOR),
        Const(4, COLOR),
    ),
)


def _full_demos(train: Corpus, label: str) -> tuple[Demonstration, ...]:
    return tuple(
        Demonstration(task_id=entry.task.task_id, kind=DemonstrationKind.FULL_SOLUTION)
        for entry in train.entries
        if entry.meta is not None and entry.meta.label == label
    )


def _top_task_ids(train: Corpus) -> tuple[str, ...]:
    return tuple(
        entry.task.task_id
        for entry in train.entries
        if entry.meta is not None and entry.meta.label == "top"
    )


def build() -> LadderSpec:
    """Construct the ``al1-mirror`` LadderSpec from the committed testbed."""
    train, heldout = split_by_meta(load_testbed("al1-mirror"))
    floor = Library(
        name="al1-L0",
        primitives=(D4_LIBRARY.get("flip_h"), D4_LIBRARY.get("flip_v"), MAP_COLOR),
    )
    budget = Budget(depth_limit=2, max_arity=2, max_pool=300)
    reference_config = Config(
        library=floor,
        search_engine=BottomUpSearchEngine(
            constant_sources=("finite-enumerate",),  # map_color needs COLOR constants
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=budget,
        learn=LearnSpec(
            learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()),
            iterations=5,
        ),
    )
    return LadderSpec(
        reference_config=reference_config,
        rungs=(
            Rung(
                level=1,
                target_abstraction=TargetAbstraction(name="rot180", template=_ROT180),
                demonstrations=_full_demos(train, "rot180"),
            ),
            Rung(
                level=2,
                target_abstraction=TargetAbstraction(
                    name="mirror_recolor", template=_MIRROR_RECOLOR
                ),
                demonstrations=_full_demos(train, "mirror_recolor"),
            ),
        ),
        top=TopRung(task_ids=_top_task_ids(train), reference_solutions=(_TOP,)),
        train_corpus=train,
        heldout_corpus=heldout,
        budgets=(budget,),
    )
