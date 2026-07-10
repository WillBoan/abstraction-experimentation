"""Tests for the learning loop: antiunification helpers + the E1 end-to-end experiment."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from pathlib import Path

import pytest

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.core.task import Task
from arc_lab.solvers.dsl.analysis.artifact import RunSpec, TaskRecord
from arc_lab.solvers.dsl.analysis.compression import CompressionMetric, SolvedTask, TwoPartMDL
from arc_lab.solvers.dsl.analysis.runner import RunSummary
from arc_lab.solvers.dsl.analysis.transfer import Usefulness, heldout_transfer, train_usefulness
from arc_lab.solvers.dsl.learn.antiunify import (
    AntiunifyPairs,
    FrequentSubtree,
    SearchScopedFrequentSubtree,
    TypeScopedFrequentSubtree,
    _antiunify,
    _close_template,
    match,
    rewrite_with,
)
from arc_lab.solvers.dsl.learn.experiments import (
    CorrelationPoint,
    StudyReport,
    StudySpec,
    _d4_targets,
    _mirror,
    compression_transfer_correlation,
    e1_rot90,
    e2_swap_cells,
    e3_swap_cols,
    e4_swap_cols_mdl,
    e5_rederive_rot90,
    e6_rederive_d4,
    e7_rederive_d4_safe,
    e8_mirror_index_sub,
    e9_mirror_index_affine,
    run_study,
)
from arc_lab.solvers.dsl.learn.selection import GreedyMDL
from arc_lab.solvers.dsl.learn.sleep import GreedyMDLSleep
from arc_lab.solvers.dsl.search import BuildGridSearch
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.primitives.build import BUILD_LIBRARY
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Input, Lam, Param, Program, Var
from arc_lab.solvers.dsl.substrate.types import COLOR, GRID, INT

_G = GRID
_C = COLOR
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
    i = INT
    a = Apply("read", (Input(), Const(0, i), Const(0, i)))
    b = Apply("read", (Input(), Const(1, i), Const(1, i)))
    template = _close_template(_antiunify(a, b, _GEN, {}, itertools.count()))
    assert template == Apply("read", (Param(0, _G), Param(1, i), Param(1, i)))


def test_match_binds_and_rejects() -> None:
    template: Program = Apply("transpose", (Apply("flip_h", (Param(0, _G),)),))
    program: Program = Apply("transpose", (Apply("flip_h", (Input(),)),))
    assert match(template, program) == (Input(),)
    assert match(template, Apply("flip_h", (Input(),))) is None


def test_rewrite_folds_the_whole_program_when_the_root_matches() -> None:
    # The original root-only behaviour is preserved as a special case.
    template: Program = Apply("flip_h", (Param(0, _G),))
    program: Program = Apply("flip_h", (Input(),))
    assert rewrite_with(program, "abs", template) == Apply("abs", (Input(),))


def test_rewrite_folds_a_matching_subtree() -> None:
    # The template matches a proper *subtree*, not the root — the capability root-only lacked.
    template: Program = Apply("flip_h", (Param(0, _G),))
    program: Program = Apply("transpose", (Apply("flip_h", (Input(),)),))
    assert rewrite_with(program, "abs", template) == Apply("transpose", (Apply("abs", (Input(),)),))


def test_rewrite_folds_nested_occurrences() -> None:
    # A match's own arguments are rewritten, so stacked occurrences all fold.
    template: Program = Apply("flip_h", (Param(0, _G),))
    program: Program = Apply("flip_h", (Apply("flip_h", (Input(),)),))
    assert rewrite_with(program, "abs", template) == Apply("abs", (Apply("abs", (Input(),)),))


# -- antiunify learns the lambda-index nodes (Lam / Var) -----------------


def _transpose_build_grid(g: Program) -> Program:
    # build_grid(width(g), height(g), lam(lam(read(g, $0, $1)))) over a grid sub-program `g`.
    body = Apply("read", (g, Var(0, INT), Var(1, INT)))
    return Apply("build_grid", (Apply("width", (g,)), Apply("height", (g,)), Lam(Lam(body))))


def test_close_template_lifts_input_inside_a_lambda_body() -> None:
    # Every Input (including the one *inside* the lam body) lifts to one grid Param, so the
    # build_grid template closes and mints as an arity-1 abstraction — loop vars ($i) stay internal.
    template = _close_template(_transpose_build_grid(Input()))
    assert not any(isinstance(n, Input) for n in template.walk())
    assert make_abstraction("t", template, BUILD_LIBRARY).param_types == (_G,)


def test_rewrite_folds_a_build_grid_program() -> None:
    # match/rewrite descend through Lam, so a whole build_grid program collapses to abs(input).
    program = _transpose_build_grid(Input())
    template = _close_template(program)
    assert rewrite_with(program, "abs", template) == Apply("abs", (Input(),))


def _build_grid_with_col(col: Program) -> Program:
    g = Input()
    body = Apply("read", (g, Var(0, INT), col))
    return Apply("build_grid", (Apply("width", (g,)), Apply("height", (g,)), Lam(Lam(body))))


def test_bound_var_safe_proposer_refuses_to_hoist_a_bound_var() -> None:
    # Two build_grid programs differing only in a *bound-var* coordinate. The naive proposer holes
    # the $i into an abstraction param (unsound — the E6 break); the bound-var-safe one refuses, so
    # no sound cross-member generalisation exists and it offers nothing (E7's fix).
    p = _build_grid_with_col(Var(1, INT))  # col = $1
    q = _build_grid_with_col(  # col = width - $1 - 1 (a reflection, contains $1)
        Apply(
            "sub",
            (
                Apply("sub", (Apply("width", (Input(),)), Var(1, INT))),
                Const(1, INT),
            ),
        )
    )
    assert len(AntiunifyPairs().propose([p, q], BUILD_LIBRARY)) >= 1
    assert AntiunifyPairs(bound_var_safe=True).propose([p, q], BUILD_LIBRARY) == []


def test_e6_and_e7_target_the_full_d4_ladder() -> None:
    ladder = ("transpose", "flip_h", "flip_v", "rot90", "rot180", "rot270")
    for factory in (e6_rederive_d4, e7_rederive_d4_safe):
        assert tuple(name for name, _ in factory().targets) == ladder
    # The whole point of the pair: e7 swaps in the bound-var-safe proposer, e6 does not.
    e6_prop, e7_prop = e6_rederive_d4().sleep.proposer, e7_rederive_d4_safe().sleep.proposer
    assert e6_prop.kind == "antiunify-pairs" and e6_prop.bound_var_safe is False
    assert e7_prop.kind == "antiunify-pairs" and e7_prop.bound_var_safe is True


# -- frequent-subtree proposers + the mirror_index bootstrap (E8 / E9) ---


_MIRROR = _mirror(Param(0, INT), Param(1, INT))  # sub(sub(#0,#1),1), the idiom


def _d4_member_programs() -> list[Program]:
    return list(_d4_targets(Input()).values())  # the six build_grid members over the input grid


def test_rewrite_folds_inside_a_lambda_body() -> None:
    # The rewrite fix: fold a coordinate idiom that sits *inside* a build_grid's lam(lam(...)) body.
    rot90 = _d4_targets(Input())["rot90"]
    folded = rewrite_with(rot90, "m", _MIRROR)
    assert "m(width(input), $1)" in str(folded)  # the mirror was folded, under the binder
    assert "sub(sub(" not in str(folded)
    # A member without the idiom is untouched.
    transpose = _d4_targets(Input())["transpose"]
    assert rewrite_with(transpose, "m", _MIRROR) == transpose


def test_frequent_subtree_mines_mirror_index_and_read_bodies() -> None:
    # The naive miner surfaces the reusable coordinate factor (mirror_index) — but *also* the larger,
    # unreusable COLOR read-body idioms greedy MDL prefers (the compression/reusability divergence).
    proposed = FrequentSubtree().propose(_d4_member_programs(), BUILD_LIBRARY)
    assert _MIRROR in proposed
    assert any(isinstance(t, Apply) and t.primitive == "read" for t in proposed)


def test_search_scoped_proposer_keeps_only_composable_idioms() -> None:
    # Scoping invention to what the search composes (INT^n->INT, derived from the search itself)
    # keeps mirror_index and drops the COLOR read-bodies.
    composes = BuildGridSearch().composes_signature
    proposed = SearchScopedFrequentSubtree(composes=composes).propose(
        _d4_member_programs(), BUILD_LIBRARY
    )
    assert _MIRROR in proposed
    assert all(t.result_type(BUILD_LIBRARY) == INT for t in proposed)
    assert not any(isinstance(t, Apply) and t.primitive == "read" for t in proposed)


def test_type_scoped_proposer_filters_by_declared_type() -> None:
    # The declared-type stopgap: only INT idioms survive (mirror_index in, COLOR read-bodies out).
    proposed = TypeScopedFrequentSubtree(result_type=INT).propose(
        _d4_member_programs(), BUILD_LIBRARY
    )
    assert _MIRROR in proposed
    assert all(t.result_type(BUILD_LIBRARY) == INT for t in proposed)


def test_naive_selects_read_body_but_scoped_selects_mirror_index() -> None:
    # The divergence and its fix, at the governance seam: with members recurring (as the wake corpus
    # has them), greedy MDL over the *naive* proposer mints a read-body; the *search-scoped* proposer
    # (mine only what the search reuses) recovers mirror_index.
    corpus = [_solved(_dummy_task(f"t{i}"), p) for i in range(3) for p in _d4_member_programs()]
    composes = BuildGridSearch().composes_signature
    naive = GreedyMDL().select(corpus, BUILD_LIBRARY, FrequentSubtree(), TwoPartMDL())
    scoped = GreedyMDL().select(
        corpus, BUILD_LIBRARY, SearchScopedFrequentSubtree(composes=composes), TwoPartMDL()
    )
    assert (
        isinstance(naive, Apply) and naive.primitive == "read"
    )  # greedy grabs the unreusable idiom
    assert scoped == _MIRROR  # scoping recovers the reusable factor


def test_e8_and_e9_target_mirror_index_via_search_scoped_proposer() -> None:
    for factory in (e8_mirror_index_sub, e9_mirror_index_affine):
        exp = factory()
        assert tuple(name for name, _ in exp.targets) == ("mirror_index",)
        assert exp.sleep.proposer.kind == "search-scoped"
    assert e8_mirror_index_sub().starting_library.name == "build"  # sub-only grammar
    assert e9_mirror_index_affine().starting_library.name == "build-affine"  # + add/mul


def test_propose_recurring_program_yields_lifted_template() -> None:
    program = Apply("transpose", (Apply("flip_h", (Input(),)),))
    candidates = AntiunifyPairs().propose([program, program, program], _GEN)
    assert Apply("transpose", (Apply("flip_h", (Param(0, _G),)),)) in candidates


# -- governance (the AbstractionSelector plug point) --------------------


def _dummy_task(task_id: str) -> Task:
    return Task.from_dict(
        task_id, {"train": [{"input": [[0]], "output": [[0]]}], "test": [{"input": [[0]]}]}
    )


def _solved(task: Task, program: Program) -> SolvedTask:
    return SolvedTask(AnnotatedTask(task), program)


def test_greedy_mdl_selects_the_compressing_template() -> None:
    # Two tasks solved by the same depth-2 word: folding both into one abstraction lowers DL,
    # so GreedyMDL must pick the closed template (the seam GreedyMDLSleep delegates to).
    program: Program = Apply("transpose", (Apply("flip_h", (Input(),)),))
    corpus = [_solved(_dummy_task("t1"), program), _solved(_dummy_task("t2"), program)]
    chosen = GreedyMDL().select(corpus, _GEN, AntiunifyPairs(), CompressionMetric())
    assert chosen == Apply("transpose", (Apply("flip_h", (Param(0, _G),)),))


def test_greedy_mdl_returns_none_when_nothing_compresses() -> None:
    # A single non-recurring program yields no useful candidate, so nothing is minted.
    program: Program = Apply("flip_h", (Input(),))
    corpus = [_solved(_dummy_task("t1"), program)]
    assert GreedyMDL().select(corpus, _GEN, AntiunifyPairs(), CompressionMetric()) is None


# -- the sleep step as a pluggable strategy (the Phase-A seam) -----------


def test_greedy_mdl_sleep_mints_rewrites_and_scores() -> None:
    # GreedyMDLSleep is the historical sleep step as a strategy: over the recurring D4 corpus it
    # must mint the search-composable idiom, rewrite the corpus to call it, and return a score
    # (lower = better) below the un-compressed baseline — the loop's convergence signal.
    corpus = [_solved(_dummy_task(f"t{i}"), p) for i in range(3) for p in _d4_member_programs()]
    metric = TwoPartMDL()
    baseline = metric.describe(corpus, BUILD_LIBRARY).total
    proposer = SearchScopedFrequentSubtree(composes=BuildGridSearch().composes_signature)
    outcome = GreedyMDLSleep(proposer, metric=metric).run(corpus, BUILD_LIBRARY, 0)
    assert any(p.template == _MIRROR for p in outcome.added)  # minted mirror_index
    assert outcome.library.version > BUILD_LIBRARY.version  # library grew
    assert all("sub(sub(" not in str(st.program) for st in outcome.corpus)  # folded, no raw idiom
    assert outcome.score < baseline  # the step compresses


def test_greedy_mdl_sleep_is_dry_when_nothing_compresses() -> None:
    # No recurrence -> no candidate -> no mint; the outcome is empty and scores the input as-is.
    program: Program = Apply("flip_h", (Input(),))
    corpus = [_solved(_dummy_task("t1"), program)]
    outcome = GreedyMDLSleep(AntiunifyPairs()).run(corpus, _GEN, 0)
    assert outcome.added == ()
    assert outcome.library is _GEN and outcome.corpus == corpus


# -- E1 end-to-end (the mechanism DoD gate) -----------------------------


def test_e1_learns_rot90_compresses_and_speeds_up(tmp_path: Path) -> None:
    report = run_study(e1_rot90(), testbeds_root=tmp_path / "testbeds", runs_root=tmp_path / "runs")

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
    run_study(e1_rot90(), testbeds_root=tmp_path / "testbeds", runs_root=tmp_path / "runs")
    testbed = tmp_path / "testbeds" / "e1-rot90"
    assert (testbed / "manifest.json").exists()
    assert list((testbed / "tasks").glob("*.json"))


def _run(exp_fn: Callable[[], StudySpec], tmp_path: Path) -> StudyReport:
    return run_study(exp_fn(), testbeds_root=tmp_path / "testbeds", runs_root=tmp_path / "runs")


@pytest.mark.slow
def test_e2_learns_fixed_cell_swap(tmp_path: Path) -> None:
    report = _run(e2_swap_cells, tmp_path)
    assert report.check.matched == ("swap_cells",)
    assert len(report.learned) == 1  # no variable-sharing needed, no bloat
    assert report.compare["L2"].considered_total < report.compare["L1"].considered_total
    assert len(report.enablement) > 0


@pytest.mark.slow
def test_e3_variable_sharing_works_but_flat_mdl_bloats(tmp_path: Path) -> None:
    report = _run(e3_swap_cols, tmp_path)
    # Variable-sharing produced the correct general swap (behaviorally matched)...
    assert "swap_cols" in report.check.matched
    # ...but the flat library cost still admits a few marginal specialisations (the finding).
    assert len(report.check.novel) > 0
    # The loop hardening (library-dedup + DL-stop) caps the runaway: no cross-generation
    # re-minting, so a handful of specialisations, not the pre-hardening 16.
    assert len(report.learned) <= 5


@pytest.mark.slow
def test_e4_two_part_mdl_eliminates_bloat(tmp_path: Path) -> None:
    report = _run(e4_swap_cols_mdl, tmp_path)
    assert report.check.matched == ("swap_cols",)
    assert report.check.novel == ()  # bloat gone
    assert len(report.learned) == 1


@pytest.mark.slow
def test_e5_rederives_rot90_as_build_grid(tmp_path: Path) -> None:
    # The keystone payoff: starting from the cell-render floor (no D4 primitive), the loop learns
    # a single size-general build_grid program behaviorally == rot90 — pixels->D4, via BuildGridSearch.
    report = _run(e5_rederive_rot90, tmp_path)
    assert report.check.matched == ("rot90",)
    assert report.check.missed == ()
    assert len(report.learned) == 1  # the size-general build_grid program, no bloat
    assert (
        len(report.enablement) > 0
    )  # with the abstraction, a depth-1 apply solves; without, it can't


# -- transfer grade + train-side usefulness (the measurement layer) -----


def _summary(rows: dict[str, tuple[bool, int]]) -> RunSummary:
    """A minimal RunSummary from ``{task_id: (solved, considered)}`` for metric unit tests."""
    records = tuple(
        TaskRecord(
            task_id=tid,
            solved=solved,
            search_solved=solved,
            considered=considered,
            program=None,
            program_size=None,
            program_dict=None,
            stats_extra={},
        )
        for tid, (solved, considered) in rows.items()
    )
    return RunSummary(
        spec=RunSpec(solver="s", dataset="d", library={}),
        records=records,
        library_bits=0.0,
        program_bits=0.0,
    )


def test_heldout_transfer_is_the_heldout_slice_of_new_solves() -> None:
    heldout = frozenset({"h1", "h2"})
    base = _summary({"t1": (True, 100), "t2": (False, 100), "h1": (False, 10), "h2": (False, 10)})
    aug = _summary({"t1": (True, 40), "t2": (True, 40), "h1": (True, 5), "h2": (False, 5)})
    # Only h1: a held-out task newly solved. h2 stays unsolved; t2 is train, not held-out.
    assert heldout_transfer(base, aug, heldout) == frozenset({"h1"})


def test_train_usefulness_is_train_only_speedup_and_enablement() -> None:
    train = frozenset({"t1", "t2"})
    base = _summary({"t1": (True, 100), "t2": (False, 100), "h1": (False, 10)})
    aug = _summary({"t1": (True, 40), "t2": (True, 40), "h1": (True, 5)})
    use = train_usefulness(base, aug, base, aug, train)  # deep pair, shallow pair (same fixtures)
    assert use.enabled == frozenset({"t2"})  # newly solved on train (shallow pair)
    assert use.speedup == 200 / 80  # deep train considered 200 -> 80; the held-out task excluded


@pytest.mark.slow
def test_e5_reports_heldout_grade_and_train_usefulness(tmp_path: Path) -> None:
    exp = e5_rederive_rot90()
    train_ids = frozenset(g.task_id for g in exp.tasks if g.split == "train")
    heldout_ids = frozenset(g.task_id for g in exp.tasks if g.split == "heldout")
    assert heldout_ids  # the testbed carries a real held-out split

    report = run_study(exp, testbeds_root=tmp_path / "testbeds", runs_root=tmp_path / "runs")

    # The grade is exactly the held-out slice of same-corpus enablement, never a train task.
    assert report.heldout <= report.enablement
    assert report.heldout <= heldout_ids
    assert report.heldout.isdisjoint(train_ids)
    # Train-side usefulness: a proper Usefulness restricted to train.
    assert isinstance(report.usefulness, Usefulness)
    assert report.usefulness.enabled <= train_ids
    assert report.usefulness.speedup > 0


def test_compression_transfer_correlation_returns_a_point_per_experiment(tmp_path: Path) -> None:
    points = compression_transfer_correlation(
        ["e1-rot90"], testbeds_root=tmp_path / "testbeds", runs_root=tmp_path / "runs"
    )
    assert [p.name for p in points] == ["e1-rot90"]
    point = points[0]
    assert isinstance(point, CorrelationPoint)
    assert point.compression > 0
    assert point.transfer >= 0
    assert point.learned >= 1
