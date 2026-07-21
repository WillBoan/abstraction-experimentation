"""The bounded rewrite engine: normalization + shallow-equivalent detection (the al7 collapse)."""

from __future__ import annotations

from arc_lab.program_search.analysis.rewrite import (
    RewriteLimits,
    normal_form,
    shallow_equivalent,
)
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.spec import LadderSpec
from arc_lab.program_search.substrate.abstraction import unfold_program
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.primitives.layout import CONCAT_H, CONCAT_V
from arc_lab.program_search.substrate.program import Apply, Lam, Param, Program, Var
from arc_lab.program_search.substrate.types import GRID

_FLOOR = Library(name="d4+concat", primitives=(*D4_LIBRARY.primitives, CONCAT_H, CONCAT_V))
_LIMITS = RewriteLimits()
_X = Param(0, GRID)
_Y = Param(1, GRID)


def _nf(program: Program) -> Program | None:
    return normal_form(program, _FLOOR, _LIMITS)


def test_involutions_collapse() -> None:
    assert _nf(Apply("flip_h", (Apply("flip_h", (_X,)),))) == _X


def test_flips_push_through_concat() -> None:
    pushed = _nf(Apply("flip_h", (Apply("concat_h", (_X, _Y)),)))
    assert pushed == Apply("concat_h", (Apply("flip_h", (_Y,)), Apply("flip_h", (_X,))))


def test_d4_chains_canonicalize() -> None:
    assert _nf(Apply("rot90", (Apply("rot90", (_X,)),))) == Apply("rot180", (_X,))
    assert _nf(Apply("identity", (_X,))) == _X


def test_normalization_is_idempotent() -> None:
    term = Apply("flip_v", (Apply("concat_v", (Apply("flip_h", (_X,)), _Y)),))
    once = _nf(term)
    assert once is not None
    assert _nf(once) == once


def test_caps_and_higher_order_content_return_none() -> None:
    term = Apply("concat_h", (_X, Apply("concat_v", (_X, _Y))))
    assert normal_form(term, _FLOOR, RewriteLimits(max_nodes=3)) is None
    assert _nf(Lam(param_type=GRID, body=Var(index=0, value_type=GRID))) is None


def _floor_form(spec_name: str, rung_name: str) -> tuple[Program, LadderSpec]:
    spec = make_ladder(spec_name)
    rung = next(rung for rung in spec.rungs if rung.name == rung_name)
    full_lib = spec.oracle_library(len(spec.rungs))
    return unfold_program(rung.template, full_lib), spec


def test_the_al7_doubling_collapse_is_found() -> None:
    # tall4's unfolded form and stack2(stack2 g)'s normalize identically (the flips cancel via
    # distribution + involution; the interchange sorts the blocks) -- the r_2k == r2^k law,
    # found as a depth-2 witness over L_2 (skipping wide4) despite tall4's own jump depth
    # passing the depth sandwich.
    target, spec = _floor_form("al7-fast-tower", "tall4")
    witness = shallow_equivalent(target, spec.oracle_library(2), spec.floor(), depth_limit=2)
    assert witness is not None and witness.depth == 2
    assert witness.term == Apply("stack2", (Apply("stack2", (Param(0, GRID),)),))


def test_no_shallow_witness_where_the_ladder_is_sound() -> None:
    # wide4 over L_1 (floor + mirror) has no depth-2 equivalent: stack2 does not exist yet and
    # its unfolding is depth-3 material. The engine finding nothing proves nothing -- but here
    # it agrees with the certificate's tractable verdict for that jump.
    target, spec = _floor_form("al7-fast-tower", "wide4")
    assert shallow_equivalent(target, spec.oracle_library(1), spec.floor(), 2) is None


def test_a_terms_cap_is_a_silent_pass() -> None:
    target, spec = _floor_form("al7-fast-tower", "tall4")
    capped = shallow_equivalent(
        target,
        spec.oracle_library(2),
        spec.floor(),
        depth_limit=2,
        limits=RewriteLimits(max_terms=1),
    )
    assert capped is None
