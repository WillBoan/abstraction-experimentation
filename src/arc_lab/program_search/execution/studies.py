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
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.program import Apply, Param
from arc_lab.program_search.substrate.types import GRID

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


#: StudySpec registry for the CLI (`arc-lab run-study <name>`).
STUDIES: dict[str, Callable[[], StudySpec]] = {
    "e1-rot90": e1_rot90,
}


def make_study(name: str) -> StudySpec:
    """Resolve a study name to a freshly built :class:`StudySpec`."""
    try:
        return STUDIES[name]()
    except KeyError:
        known = ", ".join(sorted(STUDIES))
        raise KeyError(f"unknown study {name!r}; known: {known}") from None
