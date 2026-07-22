"""The evaluation-backed lint checks (``ladders/checks.py``): constancy + conditionals."""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.program_search.ladders.checks import conditional_findings, constancy_findings
from arc_lab.program_search.ladders.shape import LintFinding
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.program import Apply, Const, If, Input, Program
from arc_lab.program_search.substrate.types import BOOL, GRID, INT


def _sub(a: int, b: int) -> int:
    return a - b


def _shift(g: Grid, n: int) -> Grid:
    return g


def _wide(g: Grid) -> bool:
    return g.width > 2


def _boom(g: Grid) -> int:
    raise ValueError("partial off its domain")


_LIB = Library(
    name="checks-test",
    primitives=(
        Primitive(name="sub", param_types=(INT, INT), return_type=INT, impl=_sub),
        Primitive(name="shift", param_types=(GRID, INT), return_type=GRID, impl=_shift),
        Primitive(name="wide", param_types=(GRID,), return_type=BOOL, impl=_wide),
        Primitive(name="boom", param_types=(GRID,), return_type=INT, impl=_boom),
    ),
)

#: Two distinct train inputs; max dimension 3, so finite-enumerate's INT domain is 0..3.
_G1 = Grid.from_list([[1, 2], [3, 4]])
_G2 = Grid.from_list([[5, 6, 7]])
_INPUTS = {"t": (_G1, _G2)}

#: shift(input, sub(2, 1)) — the composite index is train-constant 1, and 1 is enumerable.
_CONSTANT_INDEX: Program = Apply("shift", (Input(), Apply("sub", (Const(2, INT), Const(1, INT)))))


def _one(findings: tuple[LintFinding, ...]) -> LintFinding:
    assert len(findings) == 1
    return findings[0]


def test_constancy_errors_when_the_beating_literal_is_enumerated() -> None:
    finding = _one(
        constancy_findings([("t", _CONSTANT_INDEX)], _INPUTS, _LIB, ("finite-enumerate",))
    )
    assert not finding.ok and finding.severity == "error"
    assert "sub(2, 1)=1" in finding.detail


def test_constancy_warns_when_no_constant_source_mints_the_value() -> None:
    finding = _one(constancy_findings([("t", _CONSTANT_INDEX)], _INPUTS, _LIB, ()))
    assert not finding.ok and finding.severity == "warn"


def test_constancy_skips_erroring_subterms_and_short_tasks() -> None:
    # A partial primitive erroring on a train input is skipped, never flagged.
    erroring: Program = Apply("shift", (Input(), Apply("boom", (Input(),))))
    finding = _one(constancy_findings([("t", erroring)], _INPUTS, _LIB, ("finite-enumerate",)))
    assert finding.ok
    # One train example: everything is trivially constant, so the task is skipped outright
    # (min-2-train-examples owns that defect).
    single = {"t": (_G1,)}
    assert constancy_findings([("t", _CONSTANT_INDEX)], single, _LIB, ("finite-enumerate",)) == ()


def test_a_bare_literal_is_never_flagged() -> None:
    # A Const is depth 0 -- nothing shallower beats it; only COMPOSITE subterms carry the law.
    literal_only: Program = Apply("shift", (Input(), Const(1, INT)))
    finding = _one(constancy_findings([("t", literal_only)], _INPUTS, _LIB, ("finite-enumerate",)))
    assert finding.ok


def test_conditional_flags_a_condition_constant_across_train_examples() -> None:
    degenerate: Program = If(cond=Const(True, BOOL), then=Input(), orelse=Input())
    finding = _one(conditional_findings([("t", degenerate)], _INPUTS, _LIB))
    assert not finding.ok and finding.severity == "error"


def test_conditional_passes_when_both_branches_are_exercised() -> None:
    # wide(input) is False on the 2x2 grid and True on the 1x3 -- both truth values observed.
    varying: Program = If(cond=Apply("wide", (Input(),)), then=Input(), orelse=Input())
    finding = _one(conditional_findings([("t", varying)], _INPUTS, _LIB))
    assert finding.ok


def test_conditional_emits_nothing_without_branching() -> None:
    assert conditional_findings([("t", _CONSTANT_INDEX)], _INPUTS, _LIB) == ()
