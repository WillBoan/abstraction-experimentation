"""Depth: the generation a program is composed at vs the budget that puts it in reach.

The lambda cases are pinned against MEASUREMENTS of the real engine (2026-07-22). The two
`build_grid` programs below are the ones that exposed the original off-by-one: both were reported
as depth 1 when a `Lam` counted as a leaf, and both are in fact composed at generation 2.
"""

from __future__ import annotations

from arc_lab.program_search.analysis.depth import (
    Frame,
    compositional_depth,
    frames,
    min_depth_limit,
    syntactic_depth,
)
from arc_lab.program_search.substrate.program import (
    AppFn,
    Apply,
    Const,
    If,
    Input,
    Lam,
    Param,
    PrimRef,
    Program,
    Var,
)
from arc_lab.program_search.substrate.types import COLOR, GRID, INT

_G, _R, _C = Input(), Var(1, INT), Var(0, INT)


def _build_grid(*args: Program) -> Apply:
    return Apply("build_grid", args)


def test_leaves_are_generation_zero() -> None:
    for leaf in (Input(), Param(0, GRID), Const(3, COLOR), Var(0, INT), PrimRef("flip_h")):
        assert compositional_depth(leaf) == 0
        assert min_depth_limit(leaf) == 0


def test_nesting_counts_constructor_nodes() -> None:
    program = Apply("flip_h", (Apply("flip_v", (Input(),)),))
    assert compositional_depth(program) == 2
    assert min_depth_limit(program) == 2


def test_depth_is_the_max_over_argument_paths_not_the_sum() -> None:
    program = Apply("map_color", (Apply("rot180", (Input(),)), Const(1, COLOR), Const(2, COLOR)))
    assert compositional_depth(program) == 2
    # A second argument of equal depth costs nothing.
    assert compositional_depth(Apply("a", (Apply("b", (_G,)), Apply("c", (_G,))))) == 2


def test_if_and_appfn_are_constructors_like_apply() -> None:
    branch = If(Apply("eq", (Apply("height", (_G,)), Apply("width", (_G,)))), Apply("f", (_G,)), _G)
    assert compositional_depth(branch) == 3  # composed by _branch_candidates at a round >= 1
    assert min_depth_limit(branch) == 3
    # A PrimRef head is a round-0 leaf, so the AppFn is the only constructor here.
    assert compositional_depth(AppFn(PrimRef("flip_h"), (_G,))) == 1


def test_a_lambda_costs_one_generation_not_zero() -> None:
    """MEASURED: found at generation 2 with depth_limit 2 (a Lam is composed at a round >= 1 and
    consumed the round after, so it is not a leaf)."""
    program = _build_grid(Const(2, INT), Const(3, INT), Lam(INT, Lam(INT, Const(0, COLOR))))
    assert compositional_depth(program) == 2
    assert min_depth_limit(program) == 2
    assert frames(program) == (Frame(depth=2, descent=0), Frame(depth=0, descent=1))


def test_a_curried_lambda_chain_still_costs_one() -> None:
    """MEASURED: generation 2, not 3 -- `_synthesize_for_hole` wraps every binder and yields the
    whole chain as ONE candidate."""
    program = _build_grid(
        Const(3, INT), Const(3, INT), Lam(INT, Lam(INT, Apply("read", (_G, _C, _R))))
    )
    assert compositional_depth(program) == 2
    assert min_depth_limit(program) == 2


def test_a_deeper_lambda_body_raises_the_budget_but_not_the_generation() -> None:
    """MEASURED (probe rows B2/B3): both are composed at generation 2, but a body of depth d one
    descent down needs `depth_limit >= d + 1`."""
    body_2 = Apply("read", (_G, Apply("sub", (_R, _R)), _C))
    b2 = _build_grid(Apply("height", (_G,)), Apply("width", (_G,)), Lam(INT, Lam(INT, body_2)))
    assert compositional_depth(b2) == 2
    assert min_depth_limit(b2) == 3

    body_3 = Apply("read", (_G, Apply("sub", (Apply("height", (_G,)), Const(1, INT))), _C))
    b3 = _build_grid(Apply("height", (_G,)), Apply("width", (_G,)), Lam(INT, Lam(INT, body_3)))
    assert compositional_depth(b3) == 2
    assert min_depth_limit(b3) == 4
    assert frames(b3) == (Frame(depth=2, descent=0), Frame(depth=3, descent=1))


def test_nested_lambdas_compound_but_siblings_do_not() -> None:
    sibling = Apply(
        "a", (Lam(INT, Apply("b", (_C,))), Lam(INT, Apply("c", (_C,))))
    )  # two hole fills, both at descent 1
    assert frames(sibling) == (
        Frame(depth=2, descent=0),  # `a` over two Lam children, each costing 1
        Frame(depth=1, descent=1),
        Frame(depth=1, descent=1),
    )
    assert min_depth_limit(sibling) == 2

    nested = Apply("a", (Lam(INT, Apply("b", (Lam(INT, Apply("c", (_C,))),))),))
    assert [f.descent for f in frames(nested)] == [0, 1, 2]
    assert min_depth_limit(nested) == 3  # the innermost body pays its two descents


def test_syntactic_depth_predicts_neither() -> None:
    body = Apply("read", (_G, Apply("sub", (Apply("height", (_G,)), Const(1, INT))), _C))
    program = _build_grid(Apply("height", (_G,)), Apply("width", (_G,)), Lam(INT, Lam(INT, body)))
    assert syntactic_depth(program) == 6
    assert compositional_depth(program) == 2
    assert min_depth_limit(program) == 4


def test_the_budget_is_never_below_the_generation() -> None:
    programs = [
        Input(),
        Apply("flip_h", (Input(),)),
        _build_grid(Const(2, INT), Const(3, INT), Lam(INT, Lam(INT, Const(0, COLOR)))),
        Apply("a", (Lam(INT, Apply("b", (Lam(INT, Apply("c", (Var(0, INT),))),))),)),
    ]
    for program in programs:
        assert min_depth_limit(program) >= compositional_depth(program)


def test_first_order_programs_collapse_to_one_number() -> None:
    """No Lam means one frame at descent 0, so all three measures agree -- which is why every
    ladder's numbers were correct under the old (wrong-for-lambdas) rule."""
    for program in (
        Input(),
        Apply("flip_h", (Input(),)),
        Apply("flip_h", (Apply("flip_v", (Input(),)),)),
        Apply("map_color", (Apply("rot180", (Input(),)), Const(1, COLOR), Const(2, COLOR))),
    ):
        assert compositional_depth(program) == min_depth_limit(program) == syntactic_depth(program)
