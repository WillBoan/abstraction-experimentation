"""``unfold_program`` / ``substitute_params``: the structural inverse of ``make_abstraction``.

Fixtures use the two-rung ``rot180`` / ``recolor_flipped`` chain (the same one
``execution/studies.py`` learns), whose depths are small enough to hand-check exactly.
"""

from __future__ import annotations

from arc_lab.program_search.analysis.depth import compositional_depth
from arc_lab.program_search.substrate.abstraction import (
    make_abstraction,
    substitute_params,
    unfold_program,
)
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.color import MAP_COLOR
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.program import Apply, Const, Input, Param
from arc_lab.program_search.substrate.types import COLOR, GRID

# -- the two-rung ladder: L0 {flip_h, flip_v, map_color} -> r1 rot180 -> r2 recolor_flipped ------

FLOOR = Library(
    name="floor",
    primitives=(D4_LIBRARY.get("flip_h"), D4_LIBRARY.get("flip_v"), MAP_COLOR),
)
ROT180_TEMPLATE = Apply("flip_h", (Apply("flip_v", (Param(0, GRID),)),))
L1 = FLOOR.extended(name="L1", extra=(make_abstraction("rot180", ROT180_TEMPLATE, FLOOR),))
RECOLOR_TEMPLATE = Apply(
    "map_color", (Apply("rot180", (Param(0, GRID),)), Param(1, COLOR), Param(2, COLOR))
)
L2 = L1.extended(name="L2", extra=(make_abstraction("recolor_flipped", RECOLOR_TEMPLATE, L1),))


def test_substitute_params_replaces_holes_with_subtrees() -> None:
    result = substitute_params(ROT180_TEMPLATE, (Input(),))
    assert result == Apply("flip_h", (Apply("flip_v", (Input(),)),))


def test_substitute_params_shares_a_repeated_hole() -> None:
    # #0 appears once here, but the arg subtree is inserted verbatim wherever the index occurs.
    template = Apply("map_color", (Param(0, GRID), Param(1, COLOR), Param(1, COLOR)))
    result = substitute_params(template, (Input(), Const(3, COLOR)))
    assert result == Apply("map_color", (Input(), Const(3, COLOR), Const(3, COLOR)))


def test_unfold_all_expands_a_single_abstraction_call_to_floor() -> None:
    call = Apply("rot180", (Input(),))
    assert unfold_program(call, L1) == Apply("flip_h", (Apply("flip_v", (Input(),)),))


def test_unfold_expand_set_is_one_level_leaving_lower_rung_folded() -> None:
    program = Apply("recolor_flipped", (Input(), Const(1, COLOR), Const(2, COLOR)))
    # expand only the top rung: recolor unfolds, but its rot180 reference stays FOLDED.
    one_level = unfold_program(program, L2, expand=frozenset({"recolor_flipped"}))
    assert one_level == Apply(
        "map_color", (Apply("rot180", (Input(),)), Const(1, COLOR), Const(2, COLOR))
    )
    # expand=None goes all the way to the floor.
    all_the_way = unfold_program(program, L2)
    assert all_the_way == Apply(
        "map_color",
        (Apply("flip_h", (Apply("flip_v", (Input(),)),)), Const(1, COLOR), Const(2, COLOR)),
    )


def test_unfold_expand_set_not_present_at_surface_is_a_noop() -> None:
    # rot180 is only reachable *inside* recolor's template; expanding {rot180} at the surface
    # (where only recolor_flipped is called) touches nothing.
    program = Apply("recolor_flipped", (Input(), Const(1, COLOR), Const(2, COLOR)))
    assert unfold_program(program, L2, expand=frozenset({"rot180"})) == program


def test_inlined_double_jump_depth_is_not_the_sum_of_jump_depths() -> None:
    # d_1 = depth(rot180 template) = 2 ; d_2 = depth(recolor template over L1) = 2.
    assert compositional_depth(ROT180_TEMPLATE) == 2
    assert compositional_depth(RECOLOR_TEMPLATE) == 2
    # inlined double jump: recolor expressed over L0 (rot180 expanded) = 3, NOT d_1 + d_2 = 4.
    inlined = unfold_program(RECOLOR_TEMPLATE, L2, expand=frozenset({"rot180"}))
    assert compositional_depth(inlined) == 3


def test_d_raw_from_a_top_solution_unfolds_far_above_its_library_depth() -> None:
    # A top solution built on recolor_flipped: depth 2 over L2, depth 4 over the floor.
    top = Apply("flip_h", (Apply("recolor_flipped", (Input(), Const(1, COLOR), Const(2, COLOR))),))
    assert compositional_depth(top) == 2
    assert compositional_depth(unfold_program(top, L2)) == 4
