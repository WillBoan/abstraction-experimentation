"""Behavioral coverage for the registered-but-unwired learn components.

``GreedyMDLLearnEngine`` + ``AntiunifyPairs`` are exercised by the studies and by
``test_learn_port``; this file covers the rest of the registered menu, whose only
(old-tree, stitch-gated) coverage would otherwise have gone with the 2026-07-15 deletion:
``FrequentSubtree`` / ``TypeScopedFrequentSubtree`` mining, ``TwoPartMDL``'s
definition charge (the E3->E4 anti-bloat governance), ``RefactoringLearnEngine``'s
two-phase library refactoring, and (dep-gated) ``StitchProposer``.
"""

from __future__ import annotations

import pytest

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.program_search.analysis.compression import CompressionMetric, SolvedTask, TwoPartMDL
from arc_lab.program_search.learn.antiunify import (
    AntiunifyPairs,
    FrequentSubtree,
    TypeScopedFrequentSubtree,
)
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine, RefactoringLearnEngine
from arc_lab.program_search.learn.stitch_shim import StitchProposer
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.program import Apply, Input, Param, Program
from arc_lab.program_search.substrate.types import GRID, INT

_GRID = Grid.from_list([[1, 2], [3, 4]])
_ROT180: Program = Apply("rot90", (Apply("rot90", (Input(),)),))
_ROT180_TEMPLATE: Program = Apply("rot90", (Apply("rot90", (Param(0, GRID),)),))


def _solved(program: Program, task_id: str) -> SolvedTask:
    example = Example(input=_GRID, output=_GRID)
    task = Task(task_id=task_id, train=(example,), test=())
    return SolvedTask(annotated=AnnotatedTask(task, None), program=program)


# -- FrequentSubtree mining -------------------------------------------------------

#: The rot180 idiom recurring INSIDE two otherwise-distinct programs — the shape
#: whole-program antiunification cannot surface (the E7 motivation).
_MINE_CORPUS: list[Program] = [
    Apply("flip_h", (_ROT180,)),
    Apply("flip_v", (_ROT180,)),
]


def test_frequent_subtree_mines_a_recurring_proper_subtree() -> None:
    proposals = FrequentSubtree().propose(_MINE_CORPUS, D4_LIBRARY)
    assert _ROT180_TEMPLATE in proposals


def test_frequent_subtree_respects_min_frequency() -> None:
    proposals = FrequentSubtree(min_frequency=3).propose(_MINE_CORPUS, D4_LIBRARY)
    assert _ROT180_TEMPLATE not in proposals


def test_type_scoped_frequent_subtree_filters_by_result_type() -> None:
    scoped_to_grid = TypeScopedFrequentSubtree(result_type=GRID).propose(_MINE_CORPUS, D4_LIBRARY)
    scoped_to_int = TypeScopedFrequentSubtree(result_type=INT).propose(_MINE_CORPUS, D4_LIBRARY)
    assert _ROT180_TEMPLATE in scoped_to_grid
    assert scoped_to_int == []  # every candidate here is grid-typed


# -- TwoPartMDL: the definition charge ---------------------------------------------


def test_two_part_mdl_charges_definition_sizes() -> None:
    grown = D4_LIBRARY.extended(
        name="d4+abs0", extra=(make_abstraction("abs0", _ROT180_TEMPLATE, D4_LIBRARY),)
    )
    flat = CompressionMetric().library_bits(grown)
    two_part = TwoPartMDL().library_bits(grown)
    # The flat metric charges names only; two-part also charges the template's size (3 nodes).
    assert two_part == flat + _ROT180_TEMPLATE.size()


def test_two_part_mdl_blocks_a_marginal_mint_the_flat_metric_accepts() -> None:
    # Two occurrences of rot180: minting saves 2 program bits but costs 1 name + a
    # 3-node definition. Flat governance (names only) accepts; two-part refuses —
    # the E3->E4 anti-bloat finding in miniature.
    corpus = (_solved(_ROT180, "t1"), _solved(_ROT180, "t2"))

    flat = GreedyMDLLearnEngine(proposer=AntiunifyPairs(), metric=CompressionMetric())
    assert [p.name for p in flat.run(D4_LIBRARY, corpus).added] == ["abs0"]

    two_part = GreedyMDLLearnEngine(proposer=AntiunifyPairs(), metric=TwoPartMDL())
    outcome = two_part.run(D4_LIBRARY, corpus)
    assert outcome.converged
    assert outcome.library == D4_LIBRARY


# -- RefactoringLearnEngine: phase 2 folds a shared factor into definitions --------


def _rot270(inner: Program) -> Program:
    for _ in range(3):
        inner = Apply("rot90", (inner,))
    return inner


def test_refactoring_engine_folds_a_shared_factor_across_definitions() -> None:
    # Three learned definitions share the rot270 chain around differing inner flips.
    # Corpus mining can never recover it (the corpus only holds the abs calls); the
    # refactor phase mines the DEFINITIONS and folds the shared factor into them.
    library = D4_LIBRARY
    for name, inner in [("abs0", "flip_h"), ("abs1", "flip_v"), ("abs2", "transpose")]:
        template = _rot270(Apply(inner, (Param(0, GRID),)))
        library = library.extended(
            name=f"{library.name}+{name}", extra=(make_abstraction(name, template, library),)
        )
    corpus = tuple(
        _solved(Apply(name, (Input(),)), f"t-{name}") for name in ("abs0", "abs1", "abs2")
    )
    engine = RefactoringLearnEngine(
        corpus_proposer=AntiunifyPairs(),
        refactor_proposer=AntiunifyPairs(),
        metric=TwoPartMDL(),
    )
    before = TwoPartMDL().describe(list(corpus), library).total

    outcome = engine.run(library, corpus)

    assert [p.name for p in outcome.added] == ["abs3"]
    minted = outcome.library.get("abs3")
    assert minted.template == _rot270(Param(0, GRID))
    # The existing definitions were refactored to call the shared factor.
    refactored = outcome.library.get("abs0").template
    assert refactored == Apply("abs3", (Apply("flip_h", (Param(0, GRID),)),))
    assert outcome.description_length < before
    # Behavior is preserved: the refactored abstraction still computes rot270 . flip_h.
    program = Apply("abs0", (Input(),))
    expected = _rot270(Apply("flip_h", (Input(),)))
    assert program.evaluate_grid(_GRID, outcome.library) == expected.evaluate_grid(
        _GRID, outcome.library
    )


def test_refactoring_engine_with_nothing_to_refactor_matches_greedy() -> None:
    # Fewer than two learned definitions: phase 2 is a no-op and the engine reduces
    # to the greedy corpus miner.
    corpus = (_solved(_ROT180, "t1"), _solved(_ROT180, "t2"))
    refactoring = RefactoringLearnEngine(
        corpus_proposer=AntiunifyPairs(), refactor_proposer=AntiunifyPairs()
    )
    greedy = GreedyMDLLearnEngine(proposer=AntiunifyPairs())

    outcome = refactoring.run(D4_LIBRARY, corpus)
    baseline = greedy.run(D4_LIBRARY, corpus)
    assert [p.name for p in outcome.added] == [p.name for p in baseline.added] == ["abs0"]
    assert outcome.description_length == baseline.description_length


# -- StitchProposer (dep-gated) -----------------------------------------------------


def test_stitch_proposer_mines_the_recurring_idiom() -> None:
    pytest.importorskip("stitch_core")
    proposals = StitchProposer().propose([_ROT180, _ROT180], D4_LIBRARY)
    assert proposals, "stitch found no candidates on a trivially compressible corpus"
    assert all(isinstance(template, Program) for template in proposals)
