"""``compositional_depth``: leaf = 0, constructor nodes add 1, ``Lam`` as a leaf by default."""

from __future__ import annotations

from arc_lab.program_search.analysis.depth import compositional_depth
from arc_lab.program_search.substrate.program import Apply, Const, Input, Lam, Param, Var
from arc_lab.program_search.substrate.types import COLOR, GRID, INT


def test_leaves_are_depth_zero() -> None:
    assert compositional_depth(Input()) == 0
    assert compositional_depth(Param(0, GRID)) == 0
    assert compositional_depth(Const(3, COLOR)) == 0


def test_nesting_counts_constructor_nodes_only() -> None:
    # flip_h(flip_v(input)) -> 2 (two Apply nodes; the input leaf is 0).
    program = Apply("flip_h", (Apply("flip_v", (Input(),)),))
    assert compositional_depth(program) == 2


def test_depth_is_the_max_over_argument_paths() -> None:
    # map_color(rot180(input), c, c) -> 1 + max(depth(rot180(input))=1, 0, 0) = 2.
    program = Apply("map_color", (Apply("rot180", (Input(),)), Const(1, COLOR), Const(2, COLOR)))
    assert compositional_depth(program) == 2


def test_lam_is_a_leaf_by_default_but_recurses_when_asked() -> None:
    lam = Lam(param_type=INT, body=Var(0, INT))
    assert compositional_depth(lam) == 0  # lam_as_leaf=True: the body is paid in a sub-search
    assert compositional_depth(lam, lam_as_leaf=False) == 1  # syntactic: Lam over its Var body

    # A higher-order application: the Lam contributes 0 as a leaf, so the apply is depth 1...
    hof = Apply("map", (lam, Input()))
    assert compositional_depth(hof) == 1
    # ...but 2 when the lambda body is counted syntactically.
    assert compositional_depth(hof, lam_as_leaf=False) == 2
