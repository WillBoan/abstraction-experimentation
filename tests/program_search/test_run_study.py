"""The STUDY activity: run_study (grid over cached recorded runs) + create_study_report."""

from __future__ import annotations

import pytest

from arc_lab.core.dataset import Corpus
from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.program_search.execution.model import Config, LearnSpec, StudySpec, TargetAbstraction
from arc_lab.program_search.execution.run_study import (
    GridCell,
    StudyResult,
    _matches_target,
    create_study_report,
    run_study,
)
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.program import Apply, Param
from arc_lab.program_search.substrate.types import GRID

# rot180 deliberately absent (as in test_activities): tasks are only solvable as rot90∘rot90,
# so sleep should mint exactly the rot180 abstraction — which is also the study's target.
_LIBRARY = Library(
    name="d4-no-rot180",
    primitives=tuple(p for p in D4_LIBRARY.primitives if p.name in ("identity", "rot90", "flip_h")),
)

_ROT180_TEMPLATE = Apply("rot90", (Apply("rot90", (Param(0, GRID),)),))

# Depth 3 solves rot180 by composition; depth 2 only via a single (learned/target) primitive —
# so the grid exhibits ENABLEMENT: L1 fails at depth 2 where L2/L3 succeed.
_DEEP = Budget(max_depth=3, max_arity=2, max_pool=200)
_SHALLOW = Budget(max_depth=2, max_arity=2, max_pool=200)


def _rot180_task(task_id: str, cells: list[list[int]]) -> Task:
    grid = Grid.from_list(cells)
    flipped = Grid(grid.array[::-1, ::-1])
    example = Example(input=grid, output=flipped)
    return Task(task_id=task_id, train=(example,), test=(example,))


_TRAIN = Corpus.of(
    "study-train",
    [_rot180_task("t1", [[1, 2], [3, 4]]), _rot180_task("t2", [[5, 6], [7, 8]])],
)
_EVAL = Corpus.of("study-eval", [_rot180_task("t3", [[9, 1], [2, 3]])])


def _spec() -> StudySpec:
    return StudySpec(
        base_config=Config(
            library=_LIBRARY,
            search_engine=BottomUpSearchEngine(
                constant_sources=(),
                function_hole_fill_mode="none",
                polymorphism_instantiation="monomorphize",
            ),
            budget=_DEEP,
            learn=LearnSpec(
                learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()), iterations=3
            ),
        ),
        budgets=(_DEEP, _SHALLOW),
        train_corpus=_TRAIN,
        eval_corpus=_EVAL,
        target_abstractions=(TargetAbstraction(name="rot180_target", template=_ROT180_TEMPLATE),),
    )


@pytest.fixture(scope="module")
def study(tmp_path_factory: pytest.TempPathFactory) -> StudyResult:
    return run_study(_spec(), runs_root=tmp_path_factory.mktemp("runs"))


def _solved(study: StudyResult, library: str, budget: Budget, corpus: str) -> object:
    return study.grid[GridCell(library, budget, corpus)].results()["solved"]


def test_run_study_grid_and_enablement(study: StudyResult) -> None:
    assert set(study.libraries) == {"L1", "L2", "L3"}
    assert len(study.grid) == 12  # 3 libraries x 2 budgets x 2 corpora
    assert study.libraries["L3"].get("rot180_target").template == _ROT180_TEMPLATE

    # deep budget: composition suffices, every library solves everything
    for library in ("L1", "L2", "L3"):
        assert _solved(study, library, _DEEP, "train") == 2
        assert _solved(study, library, _DEEP, "eval") == 1
    # shallow budget: ENABLEMENT — only the learned/target abstraction reaches rot180
    assert _solved(study, "L1", _SHALLOW, "train") == 0
    assert _solved(study, "L2", _SHALLOW, "train") == 2
    assert _solved(study, "L3", _SHALLOW, "train") == 2
    assert _solved(study, "L2", _SHALLOW, "eval") == 1  # and it TRANSFERS


def test_grid_reuses_the_learn_activitys_derived_runs(study: StudyResult) -> None:
    # the (L2, base budget) cells are the SAME recorded runs the learn activity executed
    assert study.grid[GridCell("L2", _DEEP, "train")].run_id == study.learn.train_usefulness.run_id
    assert study.learn.transfer is not None
    assert study.grid[GridCell("L2", _DEEP, "eval")].run_id == study.learn.transfer.run_id


def test_create_study_report(study: StudyResult) -> None:
    report = create_study_report(study)

    assert report["invented"] == ["abs0"]
    assert report["behavioral_check"] == [
        {"target": "rot180_target", "matched": True, "matched_by": ["abs0"]}
    ]

    grid = report["grid"]
    assert isinstance(grid, list) and len(grid) == 12
    assert all(isinstance(row["run_id"], str) for row in grid)

    effort = report["effort"]
    assert isinstance(effort, list) and len(effort) == 4  # 2 budgets x 2 corpora
    deep_train = next(
        row for row in effort if row["corpus"] == "train" and row["budget"]["max_depth"] == 3
    )
    considered = deep_train["considered"]
    assert isinstance(considered, dict) and all(
        isinstance(value, int) and value > 0 for value in considered.values()
    )

    transfer = report["transfer"]
    assert isinstance(transfer, list) and len(transfer) == 6  # 3 libraries x 2 budgets
    l2_shallow = next(
        row for row in transfer if row["library"] == "L2" and row["budget"]["max_depth"] == 2
    )
    assert l2_shallow["train_rate"] == 1.0
    assert l2_shallow["eval_rate"] == 1.0


def test_study_spec_guards() -> None:
    spec = _spec()
    with pytest.raises(ValueError, match="LEARN config"):
        StudySpec(
            base_config=spec.base_config.with_(learn=None),
            budgets=spec.budgets,
            train_corpus=_TRAIN,
            eval_corpus=_EVAL,
            target_abstractions=spec.target_abstractions,
        )
    with pytest.raises(ValueError, match="at least one budget"):
        StudySpec(
            base_config=spec.base_config,
            budgets=(),
            train_corpus=_TRAIN,
            eval_corpus=_EVAL,
            target_abstractions=spec.target_abstractions,
        )


# -- the behavioral checker directly ----------------------------------------------

_PROBES = tuple(example.input for task in _TRAIN for example in task.train)


def test_behavioral_match_is_semantic_not_syntactic() -> None:
    # flip_h∘flip_h computes identity: different template, same behavior
    double_flip = make_abstraction(
        "double_flip", Apply("flip_h", (Apply("flip_h", (Param(0, GRID),)),)), _LIBRARY
    )
    identity_target = make_abstraction("id_target", Apply("identity", (Param(0, GRID),)), _LIBRARY)
    assert _matches_target(double_flip, identity_target, _PROBES)


def test_behavioral_mismatch_is_detected() -> None:
    single_rot = make_abstraction("single_rot", Apply("rot90", (Param(0, GRID),)), _LIBRARY)
    rot180_target = make_abstraction("rot180_target", _ROT180_TEMPLATE, _LIBRARY)
    assert not _matches_target(single_rot, rot180_target, _PROBES)
