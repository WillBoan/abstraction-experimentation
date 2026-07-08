"""Tests for the Stitch boundary: Program <-> s-expression, and Stitch as a governed proposer.

The (de)serialization tests are pure and always run. The tests that actually invoke `stitch_core`
skip cleanly when the optional wheel is absent (run them with `uv run --with stitch_core pytest`),
mirroring how the dataset-dependent integration tests skip without the submodules.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.learn.sleep import GreedyMDLSleep
from arc_lab.solvers.dsl.learn.stitch_shim import StitchProposer, _compress, from_sexpr, to_sexpr
from arc_lab.solvers.dsl.substrate.primitives.build import BUILD_LIBRARY
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Input, Lam, Param, Program, Var
from arc_lab.solvers.dsl.substrate.types import ValueType

_G, _I = ValueType.GRID, ValueType.INT


def _mirror(n: Program, k: Program) -> Program:
    return Apply("sub", (Apply("sub", (n, k)), Const(1, _I)))  # (n - k) - 1


# -- to_sexpr: the substrate is already Stitch-shaped ($i / #j / lam) ----


def test_to_sexpr_prints_stitch_notation() -> None:
    # The pixels->D4 rot90 program: Var=$i, Lam=(lam ...), Apply=prefix form.
    rot90 = Apply(
        "build_grid",
        (
            Apply("width", (Input(),)),
            Apply("height", (Input(),)),
            Lam(
                Lam(
                    Apply(
                        "read",
                        (Input(), Var(0, _I), _mirror(Apply("width", (Input(),)), Var(1, _I))),
                    )
                )
            ),
        ),
    )
    assert to_sexpr(rot90) == (
        "(build_grid (width input) (height input) "
        "(lam (lam (read input $0 (sub (sub (width input) $1) 1)))))"
    )
    assert to_sexpr(Param(0, _I)) == "x0"  # a Param is a closed terminal in Stitch *input*


# -- from_sexpr: re-infer the types Stitch drops, lift a free `input` -----


def test_serialization_is_asymmetric_input_terminals_output_metavars() -> None:
    # mirror_index: params serialize to `x{j}` terminals (valid Stitch *input*), while Stitch's
    # emitted `#j` metavars decode back to Params. The two directions are deliberately not inverse.
    mirror = _mirror(Param(0, _I), Param(1, _I))
    assert to_sexpr(mirror) == "(sub (sub x0 x1) 1)"  # our program -> Stitch input
    assert from_sexpr("(sub (sub #0 #1) 1)", BUILD_LIBRARY) == mirror  # Stitch output -> our program


def test_from_sexpr_reinfers_grid_type_from_signatures() -> None:
    # The COLOR read-body: to_sexpr drops #0's GRID type; from_sexpr must recover it from `read`'s
    # and `width`'s signatures (else the minted abstraction would be mistyped).
    read_body = Apply(
        "read", (Param(0, _G), Param(1, _I), _mirror(Apply("width", (Param(0, _G),)), Param(2, _I)))
    )
    assert from_sexpr("(read #0 #1 (sub (sub (width #0) #2) 1))", BUILD_LIBRARY) == read_body


def test_from_sexpr_lifts_free_input_to_a_grid_param() -> None:
    # Stitch leaves `input` free; our abstractions are closed, so it must lift to one shared grid
    # Param (both occurrences collapse) and renumber contiguously.
    lifted = from_sexpr("(read input #0 (sub (sub (width input) #1) 1))", BUILD_LIBRARY)
    assert not any(isinstance(n, Input) for n in lifted.walk())  # closed
    grid_params = {n.index for n in lifted.walk() if isinstance(n, Param) and n.value_type == _G}
    assert len(grid_params) == 1  # both `input` occurrences collapsed to one grid param
    assert lifted.result_type(BUILD_LIBRARY) == ValueType.COLOR  # read returns a color


# -- Stitch as a governed proposer (needs the optional wheel) ------------


def test_stitch_proposer_proposes_the_read_body_on_the_raw_corpus() -> None:
    # B1: first-order Stitch on the raw D4 corpus proposes the COLOR read-body idiom (the candidate
    # greedy MDL then prefers) — the compression/reusability divergence, at the proposer seam.
    pytest.importorskip("stitch_core")
    from arc_lab.solvers.dsl.learn.experiments import _d4_targets

    corpus = list(_d4_targets(Input()).values())
    candidates = StitchProposer(first_order=True).propose(corpus, BUILD_LIBRARY)
    assert any(isinstance(t, Apply) and t.primitive == "read" for t in candidates)


def test_stitch_sleep_selects_the_read_body_first_order() -> None:
    # B1 end-to-end: GreedyMDLSleep governed by StitchProposer (Stitch invents, our metric decides)
    # mints a read-body from the raw corpus — the divergence, reproduced through the real seam.
    pytest.importorskip("stitch_core")
    from arc_lab.solvers.dsl.learn.experiments import _d4_targets

    corpus = [(_task(f"t{i}"), p) for i in range(3) for p in _d4_targets(Input()).values()]
    outcome = GreedyMDLSleep(StitchProposer(first_order=True)).run(corpus, BUILD_LIBRARY, 0)
    assert any(
        isinstance(p.template, Apply) and p.template.primitive == "read" for p in outcome.added
    )


def _task(task_id: str) -> Task:
    return Task.from_dict(
        task_id, {"train": [{"input": [[0]], "output": [[0]]}], "test": [{"input": [[0]]}]}
    )


# -- B2: library refactoring recovers a composable mirror_index ----------


def test_stitch_refactoring_recovers_composable_mirror_index(tmp_path: Path) -> None:
    # B2 (the go/no-go): e10 mines read-bodies in-house, then Stitch antiunifies their differing
    # perceiver into the general mirror_index — recovered behaviorally AND composed by BuildGridSearch
    # (the beam cliff dissolves), all WITHOUT the SearchScopedFrequentSubtree type gag.
    pytest.importorskip("stitch_core")
    from arc_lab.solvers.dsl.learn.experiments import make_experiment, run_experiment

    report = run_experiment(
        make_experiment("e10-stitch-refactor"), testbeds_root=tmp_path, runs_root=tmp_path, write=False
    )
    assert "mirror_index" in report.check.matched  # recovered on merit, no type-scoping stopgap
    assert len(report.enablement) > 0  # composable -> the tight-beam cliff dissolved


def test_stitch_compress_is_deterministic(tmp_path: Path) -> None:
    # Determinism guard: the regression locks only mean something if Stitch is reproducible. At
    # threads=1 (our default) the same input must compress identically run-to-run.
    pytest.importorskip("stitch_core")
    from arc_lab.solvers.dsl.learn.experiments import _d4_targets

    sexprs = [to_sexpr(p) for p in _d4_targets(Input()).values()]
    first = _compress(sexprs, iterations=5, max_arity=3, first_order=True, threads=1)
    second = _compress(sexprs, iterations=5, max_arity=3, first_order=True, threads=1)
    assert first == second  # StitchAbstraction is a frozen dataclass -> structural equality
