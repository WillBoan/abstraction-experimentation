"""Tests for the learning loop: antiunification helpers + the E1 end-to-end experiment."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from pathlib import Path

from arc_lab.solvers.dsl.learn.antiunify import AntiunifyPairs, _antiunify, _close_template, match
from arc_lab.solvers.dsl.learn.experiments import (
    Experiment,
    ExperimentReport,
    e1_rot90,
    e2_swap_cells,
    e3_swap_cols,
    e4_swap_cols_mdl,
    run_experiment,
)
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Input, Param, Program
from arc_lab.solvers.dsl.substrate.types import ValueType

_G = ValueType.GRID
_C = ValueType.COLOR
_GEN = Library(name="gen", primitives=(D4_LIBRARY.get("flip_h"), D4_LIBRARY.get("transpose")))


# -- antiunification helpers --------------------------------------------


def test_close_template_lifts_input_to_one_param() -> None:
    program = Apply("transpose", (Apply("flip_h", (Input(),)),))
    assert _close_template(program) == Apply("transpose", (Apply("flip_h", (Param(0, _G),)),))


def test_antiunify_holes_a_differing_position() -> None:
    # Same shape, differing leaf -> a hole there; shared structure kept.
    a = Apply("flip_h", (Const(1, _C),))
    b = Apply("flip_h", (Const(2, _C),))
    template = _close_template(_antiunify(a, b, _GEN, {}, itertools.count()))
    assert template == Apply("flip_h", (Param(0, _C),))


def test_antiunify_shares_a_repeated_difference() -> None:
    # The same differing pair (0 vs 1) at two positions -> ONE shared Param (the E3 case).
    i = ValueType.INT
    a = Apply("read", (Input(), Const(0, i), Const(0, i)))
    b = Apply("read", (Input(), Const(1, i), Const(1, i)))
    template = _close_template(_antiunify(a, b, _GEN, {}, itertools.count()))
    assert template == Apply("read", (Param(0, _G), Param(1, i), Param(1, i)))


def test_match_binds_and_rejects() -> None:
    template: Program = Apply("transpose", (Apply("flip_h", (Param(0, _G),)),))
    program: Program = Apply("transpose", (Apply("flip_h", (Input(),)),))
    assert match(template, program) == (Input(),)
    assert match(template, Apply("flip_h", (Input(),))) is None


def test_propose_recurring_program_yields_lifted_template() -> None:
    program = Apply("transpose", (Apply("flip_h", (Input(),)),))
    candidates = AntiunifyPairs().propose([program, program, program], _GEN)
    assert Apply("transpose", (Apply("flip_h", (Param(0, _G),)),)) in candidates


# -- E1 end-to-end (the mechanism DoD gate) -----------------------------


def test_e1_learns_rot90_compresses_and_speeds_up(tmp_path: Path) -> None:
    report = run_experiment(
        e1_rot90(), testbeds_root=tmp_path / "testbeds", runs_root=tmp_path / "runs"
    )

    # It learned exactly one abstraction, behaviorally equal to the target rot90.
    assert report.check.matched == ("rot90",)
    assert report.check.missed == ()

    base, learned = report.compare["L1"], report.compare["L2"]
    # Same tasks solved, but a shorter description and less search effort.
    assert learned.solved == base.solved
    assert learned.description_length < base.description_length
    assert learned.considered_total < base.considered_total
    # Under a depth-1 budget the learned abstraction enables solves the base cannot reach.
    assert len(report.enablement) > 0


def test_e1_testbed_is_written(tmp_path: Path) -> None:
    run_experiment(e1_rot90(), testbeds_root=tmp_path / "testbeds", runs_root=tmp_path / "runs")
    testbed = tmp_path / "testbeds" / "e1-rot90"
    assert (testbed / "manifest.json").exists()
    assert list((testbed / "tasks").glob("*.json"))


def _run(exp_fn: Callable[[], Experiment], tmp_path: Path) -> ExperimentReport:
    return run_experiment(
        exp_fn(), testbeds_root=tmp_path / "testbeds", runs_root=tmp_path / "runs"
    )


def test_e2_learns_fixed_cell_swap(tmp_path: Path) -> None:
    report = _run(e2_swap_cells, tmp_path)
    assert report.check.matched == ("swap_cells",)
    assert len(report.learned) == 1  # no variable-sharing needed, no bloat
    assert report.compare["L2"].considered_total < report.compare["L1"].considered_total
    assert len(report.enablement) > 0


def test_e3_variable_sharing_works_but_flat_mdl_bloats(tmp_path: Path) -> None:
    report = _run(e3_swap_cols, tmp_path)
    # Variable-sharing produced the correct general swap (behaviorally matched)...
    assert "swap_cols" in report.check.matched
    # ...but the flat library cost still admits a few marginal specialisations (the finding).
    assert len(report.check.novel) > 0
    # The loop hardening (library-dedup + DL-stop) caps the runaway: no cross-generation
    # re-minting, so a handful of specialisations, not the pre-hardening 16.
    assert len(report.learned) <= 5


def test_e4_two_part_mdl_eliminates_bloat(tmp_path: Path) -> None:
    report = _run(e4_swap_cols_mdl, tmp_path)
    assert report.check.matched == ("swap_cols",)
    assert report.check.novel == ()  # bloat gone
    assert len(report.learned) == 1
