"""The study registry: named :class:`StudySpec`\\ s for ``arc-lab run-study <name>``.

A study *takes* corpora (committed testbeds, split by their solver-invisible metadata) —
it never generates them (EXECUTION.md: generation is ``taskgen``'s own command, so a study
re-run is always a cache hit unless its inputs actually changed).

The old E1-E10 experiment suite (``solvers/dsl/learn/experiments.py``) was calibrated
against the old bespoke search strategies (``Enumerate(coord_ints=...)``,
``BuildGridSearch(beam_width=...)``); its budgets do not transfer 1:1 to the generic
bottom-up engine. Studies are therefore re-registered here as each is *recalibrated* on
the new engine (a queued experiment pass, see EXPERIMENT_QUEUE.md) — starting with E1,
whose environment maps directly.
"""

from __future__ import annotations

from collections.abc import Callable

from arc_lab.core.annotation import Split
from arc_lab.core.dataset import Corpus, load_testbed
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.color import MAP_COLOR
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.primitives.perceive import MOST_COMMON_COLOR
from arc_lab.program_search.substrate.program import Apply, Param
from arc_lab.program_search.substrate.types import COLOR, GRID

from .model.config import Config
from .model.learn_spec import LearnSpec
from .model.study_spec import StudySpec, TargetAbstraction


def split_by_meta(corpus: Corpus) -> tuple[Corpus, Corpus]:
    """Split a testbed corpus into (train, heldout) by its solver-invisible ``Split`` meta."""
    train = tuple(e for e in corpus.entries if e.meta is not None and e.meta.split is Split.TRAIN)
    heldout = tuple(
        e for e in corpus.entries if e.meta is not None and e.meta.split is Split.HELDOUT
    )
    if not train or not heldout:
        raise ValueError(f"testbed {corpus.name!r} lacks a train/heldout split in its manifest")
    return (
        Corpus(name=f"{corpus.name}:train", entries=train),
        Corpus(name=f"{corpus.name}:heldout", entries=heldout),
    )


# -- E1: re-derive rot90 from the D4 generators {flip_h, transpose} ----------------


def e1_rot90() -> StudySpec:
    """E1 smoke: starting {flip_h, transpose}, target rot90 (withheld); testbed ``e1-rot90``.

    Depth mapping from the old environment: the old ``Enumerate(max_depth=2)`` wake is
    ``max_depth=3`` here (rounds include the round-0 leaves) and the old depth-1
    enablement search is ``max_depth=2``.
    """
    generators = Library(
        name="generators",
        primitives=(D4_LIBRARY.get("flip_h"), D4_LIBRARY.get("transpose")),
    )
    train_corpus, eval_corpus = split_by_meta(load_testbed("e1-rot90"))
    deep = Budget(max_depth=3, max_arity=1, max_pool=200)
    shallow = Budget(max_depth=2, max_arity=1, max_pool=200)
    return StudySpec(
        base_config=Config(
            library=generators,
            search_engine=BottomUpSearchEngine(
                constant_sources=(),
                function_hole_fill_mode="none",
                polymorphism_instantiation="monomorphize",
                unpinned_type_var_mode="reject",
            ),
            budget=deep,
            learn=LearnSpec(
                learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()),
                iterations=5,
            ),
        ),
        budgets=(deep, shallow),
        train_corpus=train_corpus,
        eval_corpus=eval_corpus,
        target_abstractions=(
            TargetAbstraction(
                name="rot90",
                template=Apply("transpose", (Apply("flip_h", (Param(0, GRID),)),)),
            ),
        ),
    )


# -- perceive->transform: derive recolor_bg from {map_color, most_common_color} ----


def perceive_transform() -> StudySpec:
    """First perceiver-consuming abstraction: ``recolor_bg(g,c) = map_color(g, most_common_color(g), c)``.

    Testbed ``perceive-transform``: each task varies background *within* its own train
    examples (no literal ``COLOR`` constant solves all of them at once, forcing the
    perceiving composition) and fixes target color *within* a task while varying it
    *across* tasks (giving antiunify the differing literal that becomes the free
    parameter). ``finite-enumerate`` supplies ``COLOR`` constants so every target color
    is reachable, not just ones already present in an input grid.
    """
    generators = Library(name="perceivers", primitives=(MAP_COLOR, MOST_COMMON_COLOR))
    train_corpus, eval_corpus = split_by_meta(load_testbed("perceive-transform"))
    deep = Budget(max_depth=3, max_arity=2, max_pool=300)
    shallow = Budget(max_depth=2, max_arity=2, max_pool=300)
    return StudySpec(
        base_config=Config(
            library=generators,
            search_engine=BottomUpSearchEngine(
                constant_sources=("finite-enumerate",),
                function_hole_fill_mode="none",
                polymorphism_instantiation="monomorphize",
                unpinned_type_var_mode="reject",
            ),
            budget=deep,
            learn=LearnSpec(
                learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()),
                iterations=5,
            ),
        ),
        budgets=(deep, shallow),
        train_corpus=train_corpus,
        eval_corpus=eval_corpus,
        target_abstractions=(
            TargetAbstraction(
                name="recolor_bg",
                template=Apply(
                    "map_color",
                    (
                        Param(0, GRID),
                        Apply("most_common_color", (Param(0, GRID),)),
                        Param(1, COLOR),
                    ),
                ),
            ),
        ),
    )


# -- layered abstraction: L2 built ON the learned L1 -------------------------------


def layered_abstraction() -> StudySpec:
    """Multi-generation: L1 `rot180 = flip_h(flip_v(g))`; L2 `recolor_flipped(g,a,b) =
    map_color(rot180(g),a,b)` built on the learned L1 -- the cleanest test of
    abstractions-on-abstractions.

    Testbed ``layered-abstraction`` mixes both task types at ONE fixed budget
    (``max_depth=3``, two applications): raw composition reaches rot180 (two
    applications) but not recolor_flipped (three), so WAKE only solves the rot180
    tasks in iteration 0 and sleep mints ``abs0``. With ``abs0`` in the library,
    recolor_flipped collapses to two applications and WAKE genuinely re-solves it
    (not a corpus rewrite) in iteration 1, giving sleep the corpus to mint
    ``abs1 = map_color(abs0(g),a,b)``. ``iterations=5`` is a generous cap -- early
    stop halts once nothing more compresses.
    """
    generators = Library(
        name="generators",
        primitives=(D4_LIBRARY.get("flip_h"), D4_LIBRARY.get("flip_v"), MAP_COLOR),
    )
    train_corpus, eval_corpus = split_by_meta(load_testbed("layered-abstraction"))
    learn_budget = Budget(max_depth=3, max_arity=2, max_pool=300)
    deep = Budget(max_depth=4, max_arity=2, max_pool=300)
    return StudySpec(
        base_config=Config(
            library=generators,
            search_engine=BottomUpSearchEngine(
                constant_sources=("finite-enumerate",),
                function_hole_fill_mode="none",
                polymorphism_instantiation="monomorphize",
                unpinned_type_var_mode="reject",
            ),
            budget=learn_budget,
            learn=LearnSpec(
                learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()),
                iterations=5,
            ),
        ),
        budgets=(deep, learn_budget),
        train_corpus=train_corpus,
        eval_corpus=eval_corpus,
        target_abstractions=(
            TargetAbstraction(
                name="rot180",
                template=Apply("flip_h", (Apply("flip_v", (Param(0, GRID),)),)),
            ),
            TargetAbstraction(
                name="recolor_flipped",
                template=Apply(
                    "map_color",
                    (
                        Apply("flip_h", (Apply("flip_v", (Param(0, GRID),)),)),
                        Param(1, COLOR),
                        Param(2, COLOR),
                    ),
                ),
            ),
        ),
    )


#: StudySpec registry for the CLI (`arc-lab run-study <name>`).
STUDIES: dict[str, Callable[[], StudySpec]] = {
    "e1-rot90": e1_rot90,
    "perceive-transform": perceive_transform,
    "layered-abstraction": layered_abstraction,
}


def make_study(name: str) -> StudySpec:
    """Resolve a study name to a freshly built :class:`StudySpec`."""
    try:
        return STUDIES[name]()
    except KeyError:
        known = ", ".join(sorted(STUDIES))
        raise KeyError(f"unknown study {name!r}; known: {known}") from None
