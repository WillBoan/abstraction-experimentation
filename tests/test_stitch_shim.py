"""Tests for the Stitch boundary: Program <-> s-expression, and Stitch as a governed proposer.

The (de)serialization tests are pure and always run. The tests that actually invoke `stitch_core`
skip cleanly when the optional wheel is absent (run them with `uv run --with stitch_core pytest`),
mirroring how the dataset-dependent integration tests skip without the submodules.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from arc_lab.solvers.dsl.analysis.compression import SolvedTask
from arc_lab.solvers.dsl.learn.sleep import GreedyMDLSleep
from arc_lab.solvers.dsl.learn.stitch_shim import StitchProposer, _compress, from_sexpr, to_sexpr
from arc_lab.solvers.dsl.substrate.library import Library, Primitive
from arc_lab.solvers.dsl.substrate.primitives.build import BUILD_AFFINE_LIBRARY, BUILD_LIBRARY
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Input, Lam, Param, Program, Var
from arc_lab.solvers.dsl.substrate.types import BOOL, COLOR, FN, GRID, INT

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.core.task import Task

_G, _I = GRID, INT


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
    assert (
        from_sexpr("(sub (sub #0 #1) 1)", BUILD_LIBRARY) == mirror
    )  # Stitch output -> our program


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
    assert lifted.result_type(BUILD_LIBRARY) == COLOR  # read returns a color


def test_bool_consts_round_trip_through_stitch_notation() -> None:
    # BOOL literals serialize to bare `true`/`false` tokens (valid Stitch terminals) and decode back to
    # BOOL Consts. Without this a bool-bearing program would emit Python's `True`, which from_sexpr
    # cannot parse — so an `eq`/`if` idiom reaching Stitch would silently fail to round-trip.
    assert to_sexpr(Const(True, BOOL)) == "true"
    assert to_sexpr(Const(False, BOOL)) == "false"
    assert from_sexpr("true", BUILD_LIBRARY) == Const(True, BOOL)
    assert from_sexpr("false", BUILD_LIBRARY) == Const(False, BOOL)


def test_from_sexpr_scopes_bound_vars_per_binder() -> None:
    # Two *sibling* lambdas each bind their own `$0` — at different types (a grid for `width`, an int
    # for `add`). De Bruijn `$i` is relative to its binder, so these must stay independent. A flat
    # index->type map (the pre-fix bug) would unify the two `$0`s and raise `grid != int`; the binder
    # *stack* keeps them separate. `p` takes two function args (FN), the only thing special here.
    width, add = BUILD_AFFINE_LIBRARY.get("width"), BUILD_AFFINE_LIBRARY.get("add")
    p = Primitive("p", (FN, FN), _G, lambda a, b: a)
    lib = Library(name="siblings", primitives=(p, width, add))
    prog = from_sexpr("(p (lam (width $0)) (lam (add $0 1)))", lib)  # must not raise
    var_types = {str(n.value_type) for n in prog.walk() if isinstance(n, Var)}
    assert var_types == {"grid", "int"}  # the two `$0`s resolved independently


# -- Stitch as a governed proposer (needs the optional wheel) ------------


def _arity_ok(template: Program) -> bool:
    """Every Apply node has a valid arg count for its primitive (variadic = at least the fixed arity)."""
    for node in template.walk():
        if isinstance(node, Apply):
            prim = BUILD_LIBRARY.get(node.primitive)
            if (
                (len(node.args) < prim.arity)
                if prim.is_variadic
                else (len(node.args) != prim.arity)
            ):
                return False
    return True


def test_from_sexpr_rejects_arity_invalid_partial_applications() -> None:
    # First-order Stitch *curries*: on the D4 corpus it abstracts the common prefix and re-supplies the
    # varying trailing arg per call site, so it emits partial applications like a 2-arg `read` (arity 3)
    # or a 2-arg `build_grid` (arity 3). Those are not valid n-ary Applys in our non-curried DSL, so
    # from_sexpr must reject them (a ValueError the proposer catches and skips) rather than build a
    # malformed, unevaluable node that only a downstream arity guard catches by accident.
    with pytest.raises(ValueError):
        from_sexpr("(read input (sub (sub (height input) #0) 1))", BUILD_LIBRARY)  # read/3, 2 args
    with pytest.raises(ValueError):
        from_sexpr("(build_grid (#1 input) (#0 input))", BUILD_LIBRARY)  # build_grid/3, 2 args


def test_stitch_proposer_yields_only_well_formed_candidates() -> None:
    # B1, corrected: first-order Stitch on the raw D4 corpus does *not* yield a usable read-body — the
    # "read-body" it finds is the partial application above, now correctly rejected — so the proposer
    # returns only arity-valid candidates. The *well-formed* read-body idiom (the compression/reusability
    # divergence) surfaces only via the hierarchical sleep path: test_stitch_sleep_selects_..., below.
    pytest.importorskip("stitch_core")
    from arc_lab.solvers.dsl.learn.experiments import _d4_targets

    corpus = list(_d4_targets(Input()).values())
    candidates = StitchProposer(first_order=True).propose(corpus, BUILD_LIBRARY)
    assert candidates  # it still proposes something (e.g. width(#0))
    assert all(_arity_ok(c) for c in candidates)  # no malformed node leaks through


def test_stitch_sleep_selects_the_read_body_first_order() -> None:
    # B1 end-to-end: GreedyMDLSleep governed by StitchProposer (Stitch invents, our metric decides)
    # mints a read-body from the raw corpus — the divergence, reproduced through the real seam.
    pytest.importorskip("stitch_core")
    from arc_lab.solvers.dsl.learn.experiments import _d4_targets

    corpus = [
        SolvedTask(AnnotatedTask(_task(f"t{i}")), p)
        for i in range(3)
        for p in _d4_targets(Input()).values()
    ]
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
    from arc_lab.solvers.dsl.learn.experiments import make_study, run_study

    report = run_study(
        make_study("e10-stitch-refactor"),
        testbeds_root=tmp_path,
        runs_root=tmp_path,
        write=False,
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


# -- Phase F: higher-order Stitch invents, higher-order Enumerate consumes -----


def test_higher_order_stitch_invents_twice_and_hof_enumerate_consumes_it() -> None:
    # The whole higher-order stack, end to end. From a corpus of "apply a transform twice", HIGHER-order
    # Stitch invents `twice(fn, grid) = fn(fn(grid))` by holing the repeated function; FIRST-order Stitch
    # cannot (a function in head position is unholeable). The higher-order `Enumerate` then CONSUMES the
    # minted `twice` to solve rot180 at depth 1 — which the first-order search provably cannot.
    pytest.importorskip("stitch_core")
    from arc_lab.solvers.dsl.search.enumerate import Enumerate
    from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
    from arc_lab.solvers.dsl.substrate.library import Library
    from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY

    def double(name: str) -> Program:
        return Apply(name, (Apply(name, (Input(),)),))

    corpus = [double("rot90"), double("rot270"), double("flip_h")]
    assert (
        StitchProposer(first_order=True).propose(corpus, D4_LIBRARY) == []
    )  # can't hole a function
    candidates = StitchProposer(first_order=False).propose(corpus, D4_LIBRARY)
    assert candidates  # higher-order invents twice = (#0 (#0 input))

    twice = make_abstraction("twice", candidates[0], D4_LIBRARY)
    library = Library(name="d4+twice", primitives=(D4_LIBRARY.get("rot90"), twice))
    task = Task.from_dict(
        "rot180",
        {
            "train": [{"input": [[1, 2], [3, 4]], "output": [[4, 3], [2, 1]]}],
            "test": [{"input": [[1, 2], [3, 4]]}],
        },
    )
    assert Enumerate(max_depth=1).find(task, library).programs == ()  # first-order can't at depth 1
    solved = Enumerate(max_depth=1, higher_order=True).find(task, library)
    assert len(solved.programs) == 1 and "twice" in str(
        solved.programs[0]
    )  # consumed the invention
