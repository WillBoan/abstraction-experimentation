"""Behavior locks: exact solved task-id sets per preset on ``arc1-train``.

**Deliberately re-pinned (2026-07-11)** for the execution overhaul (EXECUTION.md Phase 7):
the presets are `execution/presets.py`'s `Config`s driven through the recorded-run core —
no solver classes. Continuity with the old locks (`tests/test_integration.py`, which guard
the old tree until its deletion pass):

- `d4` reproduces the old `dsl` seven EXACTLY (same task-ids).
- `synth` reproduces the old `dsl-synth` eleven EXACTLY. The lock runs at ``max_depth=2``
  (single application + constants): the old lock's empirical finding — deeper composition
  yields the identical set on this vocabulary — replicates on the new engine (verified at
  depth 3, 2026-07-11), and depth 2 keeps the lock fast.
- `beam` is newly locked (the old `dsl-beam` never was): 9 solved — `synth`'s eleven minus
  two, the beam truncation's measured cost.
- `sym` solves 10 of the old `dsl-sym` nineteen (the D4 seven + the three overlay tasks);
  the nine tile tasks are a deliberate budget/policy limit of the generic engine (see the
  `SYM_SOLVED` note). Locked on a fixed 30-task slice — the full corpus costs ~32 min.

A behavior-preserving change must not move these sets; a feature that changes them updates
this file deliberately. Locks run against a fresh ``runs_root`` (tmp) so a stale cache can
never mask a regression.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arc_lab.core.dataset import Corpus, load_dataset
from arc_lab.core.grid import Grid
from arc_lab.program_search.execution.model import RunRecord, TargetAbstraction
from arc_lab.program_search.execution.presets import PRESETS
from arc_lab.program_search.execution.run_search import run_search
from arc_lab.program_search.execution.run_search_learn import run_search_learn
from arc_lab.program_search.execution.run_study import _invented, _matches_target
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library, Primitive

pytestmark = pytest.mark.slow


def _arc1_train() -> Corpus:
    try:
        return load_dataset("arc1-train")
    except FileNotFoundError:  # submodules absent: skip cleanly (CLAUDE.md)
        pytest.skip("arc1-train dataset not available (git submodule update --init)")


def _solved_ids(record: RunRecord) -> set[str]:
    results = record.results()
    tasks = results["tasks"]
    assert isinstance(tasks, list)
    return {row["task_id"] for row in tasks if row["score"]["solved"]}


def _behavioral_check(
    invented: tuple[Primitive, ...],
    targets: tuple[TargetAbstraction, ...],
    l1: Library,
    probes: tuple[Grid, ...],
) -> list[dict[str, object]]:
    """Mirrors ``create_study_report``'s behavioral-check loop (``run_study.py``) directly off a
    learned library, with no computed grid needed — see the two ``_study_locks_`` tests below."""
    rows: list[dict[str, object]] = []
    for target in targets:
        target_primitive = make_abstraction(target.name, target.template, l1)
        matched_by = [p.name for p in invented if _matches_target(p, target_primitive, probes)]
        rows.append({"target": target.name, "matched": bool(matched_by), "matched_by": matched_by})
    return rows


#: The D4 seven — identical to the old `dsl` lock's set.
D4_SOLVED = {
    "3c9b0459",  # rot180
    "6150a2bd",  # rot180
    "67a3c6ac",  # flip_h
    "68b16354",  # flip_v
    "74dd1130",  # transpose
    "9dfd6313",  # transpose
    "ed36ccf7",  # rot90
}

#: The atomic four the `synth` vocabulary adds (one scale, three color maps) — identical
#: to the old `dsl-synth` lock's set.
SYNTH_ATOMIC = {"9172f3a0", "b1948b0a", "c59eb873", "c8f0f002"}
SYNTH_SOLVED = D4_SOLVED | SYNTH_ATOMIC

#: Beam width 32 reaches nine of `synth`'s eleven: the truncation cuts one color map and
#: one scale composite — the beam's measured cost, locked.
BEAM_SOLVED = D4_SOLVED | {"9172f3a0", "c59eb873"}

#: `sym` on the FULL arc1-train solves 10 (measured 2026-07-11, ~32 CPU-min): the D4 seven
#: plus the old `dsl-sym` lock's three OVERLAY tasks. The old lock's nine TILE tasks are NOT
#: solved — a deliberate, understood budget/policy limit of the generic engine, not a bug:
#: a 3x3 mosaic is nine variadic arguments (out of `max_arity=4`), and a tiling factor that
#: is neither input dimension is out of vocabulary under harvest-from-instance constants.
#: The lift is a structured-composition capability or budget policy, never a bespoke search.
SYM_SOLVED = D4_SOLVED | {"496994bd", "b8825c91", "f25ffba3"}

#: The sym lock's corpus: a FIXED 30-task slice — all 10 solved tasks + the 20 cheapest
#: unsolved ones (curated for signal-per-second; the full corpus costs ~32 min, unusable as
#: a gate). The slice is an explicit id list so it can never drift with the dataset order.
SYM_LOCK_TASK_IDS = (
    "05269061",
    "0d3d703e",
    "28e73c20",
    "3bd67248",
    "3c9b0459",
    "4522001f",
    "496994bd",
    "539a4f51",
    "6150a2bd",
    "67a3c6ac",
    "68b16354",
    "6f8cd79b",
    "74dd1130",
    "85c4e7cd",
    "9dfd6313",
    "a5f85a15",
    "a61f2674",
    "b0c4d837",
    "b60334d2",
    "b8825c91",
    "b8cdaf2b",
    "bbc9ae5d",
    "bda2d7a6",
    "caa06a1f",
    "e9afcf9a",
    "ea786f4a",
    "eb281b96",
    "ed36ccf7",
    "f25ffba3",
    "feca6190",
)


def test_d4_solves_exactly_the_known_seven(tmp_path: Path) -> None:
    record = run_search(PRESETS["d4"], _arc1_train(), runs_root=tmp_path)
    assert _solved_ids(record) == D4_SOLVED


def test_synth_solves_exactly_the_known_eleven(tmp_path: Path) -> None:
    # Locked at depth 2 (see module docstring); the preset itself runs depth 3.
    config = PRESETS["synth"].with_(budget=Budget(max_depth=2, max_arity=2, max_pool=500))
    record = run_search(config, _arc1_train(), runs_root=tmp_path)
    solved = _solved_ids(record)
    assert solved == SYNTH_SOLVED
    assert solved >= D4_SOLVED  # the atomic vocabulary is strictly additive over D4


def test_beam_solves_exactly_the_known_nine(tmp_path: Path) -> None:
    record = run_search(PRESETS["beam"], _arc1_train(), runs_root=tmp_path)
    solved = _solved_ids(record)
    assert solved == BEAM_SOLVED
    assert solved < SYNTH_SOLVED  # the beam truncation costs exactly synth's other two


def test_sym_solves_exactly_the_known_ten_on_the_lock_slice(tmp_path: Path) -> None:
    full = _arc1_train()
    wanted = set(SYM_LOCK_TASK_IDS)
    slice_corpus = Corpus(
        name="arc1-train-sym-lock",
        entries=tuple(e for e in full.entries if e.task.task_id in wanted),
    )
    assert len(slice_corpus) == len(SYM_LOCK_TASK_IDS)
    record = run_search(PRESETS["sym"], slice_corpus, runs_root=tmp_path)
    solved = _solved_ids(record)
    assert solved == SYM_SOLVED
    assert solved >= D4_SOLVED  # the combinators are strictly additive over D4


def test_e1_study_locks_the_learning_loop(tmp_path: Path) -> None:
    """The abstraction-formation lock: E1 on the new stack, end to end.

    Sleep mints exactly one abstraction; it behaviorally matches the withheld rot90
    target; and at the shallow (enablement) budget the learned library solves ALL
    held-out tasks where the starting library solves none of the train split.
    """
    from arc_lab.program_search.execution.run_study import GridCell, create_study_report, run_study
    from arc_lab.program_search.execution.studies import make_study

    spec = make_study("e1-rot90")
    result = run_study(spec, runs_root=tmp_path)
    report = create_study_report(result)

    assert report["invented"] == ["abs0"]
    assert report["behavioral_check"] == [
        {"target": "rot90", "matched": True, "matched_by": ["abs0"]}
    ]
    shallow = spec.budgets[1]
    assert result.grid[GridCell("L1", shallow, "train")].results()["solved"] == 0
    assert result.grid[GridCell("L2", shallow, "train")].results()["solved"] == 8
    assert result.grid[GridCell("L2", shallow, "eval")].results()["solved"] == 4


def test_perceive_transform_study_locks_the_learning_loop(tmp_path: Path) -> None:
    """The perceiver-consuming-abstraction lock: recolor_bg from {map_color, most_common_color}.

    Sleep mints exactly one abstraction, structurally `map_color(g, most_common_color(g), c)`
    (grid var-shared across both call sites) -- not merely a behavioral match, since the whole
    point is that the search is *derived through the perceiver*, not a literal reparameterization
    of `map_color`. At the shallow (enablement) budget the learned library solves every task
    (including both held-out, unseen target colors) where the starting library solves none.

    Drives the LEARN activity plus exactly the four `shallow`-budget cells these assertions need,
    rather than the full `run_study` grid (3 libraries x 2 budgets x 2 corpora = 12 cells): the
    other 8 (L3, and the "deep"-budget diagnostic) go unchecked here and are already covered
    generically and cheaply by `test_run_study.py`'s toy-corpus test — computing them on the real
    testbed only to discard the result was most of this test's wall time.
    """
    from arc_lab.program_search.execution.studies import make_study
    from arc_lab.program_search.substrate.program import Apply, Param
    from arc_lab.program_search.substrate.types import COLOR, GRID

    spec = make_study("perceive-transform")
    learn = run_search_learn(
        spec.base_config, spec.train_corpus, spec.eval_corpus, runs_root=tmp_path
    )
    l1 = spec.base_config.library
    l2 = learn.learn.learned_library()

    invented = _invented(l1, l2)
    assert [primitive.name for primitive in invented] == ["abs0"]
    probes = tuple(example.input for task in spec.train_corpus for example in task.train)
    assert _behavioral_check(invented, spec.target_abstractions, l1, probes) == [
        {"target": "recolor_bg", "matched": True, "matched_by": ["abs0"]}
    ]
    assert l2.get("abs0").template == Apply(
        "map_color",
        (Param(0, GRID), Apply("most_common_color", (Param(0, GRID),)), Param(1, COLOR)),
    )

    shallow = spec.budgets[1]
    config_l1 = spec.base_config.with_(library=l1, budget=shallow, learn=None)
    config_l2 = spec.base_config.with_(library=l2, budget=shallow, learn=None)
    assert run_search(config_l1, spec.train_corpus, runs_root=tmp_path).results()["solved"] == 0
    assert run_search(config_l1, spec.eval_corpus, runs_root=tmp_path).results()["solved"] == 0
    assert run_search(config_l2, spec.train_corpus, runs_root=tmp_path).results()["solved"] == 5
    assert run_search(config_l2, spec.eval_corpus, runs_root=tmp_path).results()["solved"] == 2


def test_layered_abstraction_study_locks_multi_generation_learning(tmp_path: Path) -> None:
    """The abstractions-on-abstractions lock: L2 minted USING the L1 learned in the same run.

    `layered-abstraction` mixes rot180 tasks (reachable at the learn budget via raw
    composition) with recolor_flipped tasks (one application too deep, raw). Sleep must
    mint `abs0 = rot180` from the rot180 tasks FIRST, so that WAKE's next iteration --
    genuinely re-searching, not rewriting -- can then reach recolor_flipped in one fewer
    application and sleep mints `abs1` built directly on `abs0`.

    Drives the LEARN activity plus exactly the four `learn_budget` cells these assertions need,
    rather than the full `run_study` grid (3 libraries x 2 budgets x 2 corpora = 12 cells): the
    other 8 (L3, and the "deep"-budget diagnostic) go unchecked here and are already covered
    generically and cheaply by `test_run_study.py`'s toy-corpus test — computing them on the real
    testbed only to discard the result was ~80% of this test's wall time (measured 2026-07-13:
    59s full grid vs 12s learn + the four needed cells).
    """
    from arc_lab.program_search.execution.studies import make_study
    from arc_lab.program_search.substrate.program import Apply, Param
    from arc_lab.program_search.substrate.types import COLOR, GRID

    spec = make_study("layered-abstraction")
    learn = run_search_learn(
        spec.base_config, spec.train_corpus, spec.eval_corpus, runs_root=tmp_path
    )
    l1 = spec.base_config.library
    l2 = learn.learn.learned_library()

    invented = _invented(l1, l2)
    assert [primitive.name for primitive in invented] == ["abs0", "abs1"]
    probes = tuple(example.input for task in spec.train_corpus for example in task.train)
    assert _behavioral_check(invented, spec.target_abstractions, l1, probes) == [
        {"target": "rot180", "matched": True, "matched_by": ["abs0"]},
        {"target": "recolor_flipped", "matched": True, "matched_by": ["abs1"]},
    ]
    assert l2.get("abs0").template == Apply("flip_h", (Apply("flip_v", (Param(0, GRID),)),))
    assert l2.get("abs1").template == Apply(
        "map_color", (Apply("abs0", (Param(0, GRID),)), Param(1, COLOR), Param(2, COLOR))
    )

    learn_budget = spec.budgets[1]
    config_l1 = spec.base_config.with_(library=l1, budget=learn_budget, learn=None)
    config_l2 = spec.base_config.with_(library=l2, budget=learn_budget, learn=None)
    assert run_search(config_l1, spec.train_corpus, runs_root=tmp_path).results()["solved"] == 4
    assert run_search(config_l1, spec.eval_corpus, runs_root=tmp_path).results()["solved"] == 1
    assert run_search(config_l2, spec.train_corpus, runs_root=tmp_path).results()["solved"] == 8
    assert run_search(config_l2, spec.eval_corpus, runs_root=tmp_path).results()["solved"] == 2
