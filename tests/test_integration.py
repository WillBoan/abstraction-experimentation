"""End-to-end tests against the vendored ARC datasets.

These require the git submodules to be initialised; they skip cleanly if not.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from arc_lab.eval.runner import run
from arc_lab.solvers import make_solver

from arc_lab.core.dataset import dataset_path, load_dataset
from arc_lab.viz import render_task

pytestmark = pytest.mark.skipif(
    not dataset_path("arc1-train").is_dir(),
    reason="ARC submodules not initialised (git submodule update --init --recursive)",
)


def test_load_real_dataset() -> None:
    ds = load_dataset("arc1-train", limit=5)
    assert len(ds) == 5
    assert all(len(task.train) >= 1 for task in ds)


def test_run_dsl_on_slice() -> None:
    ds = load_dataset("arc1-train", limit=20)
    report = run(make_solver("dsl"), ds)
    assert report.total == 20
    assert report.errored == 0
    assert 0.0 <= report.accuracy <= 1.0


# The exact set of ARC-1 training tasks solvable by a single whole-grid D4
# transform. This locks the DSL solver's behaviour: substrate refactors and new
# search strategies must not change which of these baseline tasks are solved.
_DSL_KNOWN_SOLVED = {
    "3c9b0459",  # rot180
    "6150a2bd",  # rot180
    "67a3c6ac",  # flip_h
    "68b16354",  # flip_v
    "74dd1130",  # transpose
    "9dfd6313",  # transpose
    "ed36ccf7",  # rot90
}


def test_dsl_solves_exactly_the_known_seven() -> None:
    ds = load_dataset("arc1-train")
    report = run(make_solver("dsl"), ds)
    assert report.errored == 0
    solved = {r.task_id for r in report.results if r.solved}
    assert solved == _DSL_KNOWN_SOLVED


# The symmetry solver adds the overlay (3 tasks) and tile (9 tasks) combinators on
# top of the D4 seven, all using the same eight transforms. This locks the lift.
_DSL_SYM_OVERLAY = {"496994bd", "b8825c91", "f25ffba3"}
_DSL_SYM_TILE = {
    "4c4377d9",
    "62c24649",
    "67e8384a",
    "6d0aefbc",
    "6fa7a44f",
    "7fe24cdd",
    "8be77c9e",
    "a416b8f3",
    "c9e6f938",
}
_DSL_SYM_KNOWN_SOLVED = _DSL_KNOWN_SOLVED | _DSL_SYM_OVERLAY | _DSL_SYM_TILE


@pytest.mark.slow
def test_dsl_sym_solves_exactly_nineteen() -> None:
    ds = load_dataset("arc1-train")
    report = run(make_solver("dsl-sym"), ds)
    assert report.errored == 0
    solved = {r.task_id for r in report.results if r.solved}
    assert solved == _DSL_SYM_KNOWN_SOLVED
    # The combinators are strictly additive: they never lose a D4 task.
    assert solved >= _DSL_KNOWN_SOLVED


# The synthesis solver adds four atomic-primitive tasks (one scale, three color
# maps) to the D4 seven. Run at depth 1: depth-2 composition yields the identical
# set on this vocabulary (an empirical finding), and depth 1 keeps the test fast.
_DSL_SYNTH_ATOMIC = {"9172f3a0", "b1948b0a", "c59eb873", "c8f0f002"}
_DSL_SYNTH_KNOWN_SOLVED = _DSL_KNOWN_SOLVED | _DSL_SYNTH_ATOMIC


@pytest.mark.slow
def test_dsl_synth_solves_the_atomic_eleven() -> None:
    from arc_lab.solvers.dsl.config import PRESETS
    from arc_lab.solvers.dsl.solver import ProgramSearchSolver

    ds = load_dataset("arc1-train")
    report = run(ProgramSearchSolver.from_config(PRESETS["dsl-synth"].with_param(max_depth=1)), ds)
    assert report.errored == 0
    solved = {r.task_id for r in report.results if r.solved}
    assert solved == _DSL_SYNTH_KNOWN_SOLVED
    assert solved >= _DSL_KNOWN_SOLVED


@pytest.mark.slow
def test_render_task_to_png(tmp_path: Path) -> None:
    ds = load_dataset("arc1-train", limit=1)
    out = tmp_path / "task.png"
    render_task(ds[0], save=out)
    assert out.exists() and out.stat().st_size > 0
