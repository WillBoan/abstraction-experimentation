"""The full node grammar: booleans, branching, PrimRef, Lam, Var, AppFn, negative ints.

Every construct is a Python form resolved by the TYPE OF THE POSITION it sits in
(LADDER-FORMAT.md EXP). These tests pin both directions -- elaboration and rendering -- because a
binder's *name* is arbitrary (like a `Param` index), so the round-trip is on programs, not text.
"""

from __future__ import annotations

import pytest

from arc_lab.core.geometry import Offset
from arc_lab.program_search.ladders.lang import LadderFormatError
from arc_lab.program_search.ladders.lang.expr import elaborate_expression, render_expression
from arc_lab.program_search.substrate.library import Library
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
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import (
    BOOL,
    COLOR,
    GRID,
    INT,
    OFFSET,
    ArrowType,
    Type,
    list_type,
)

_LIB = Library(
    name="ho",
    primitives=tuple(
        BASE_PRIMITIVES[name]
        for name in (
            "build_grid",
            "read",
            "height",
            "width",
            "map",
            "cells",
            "flip_h",
            "flip_v",
            "translate",
            "scale",
            "if",
            "eq",
            "most_common_color",
            "map_color",
            "add",
        )
    ),
)
_GRIDS = list_type(GRID)
_GRID_FN = ArrowType((GRID,), GRID)


def _elab(text: str, params: tuple[tuple[str, Type], ...] = ()) -> Program:
    return elaborate_expression(text, library=_LIB, params=params, allow_input=True)


def test_negative_int_literal() -> None:
    # `scale` is the INT consumer here; `translate` now takes an `Offset`, so it no longer exercises
    # a bare negative INT literal at all.
    assert _elab("scale(input, -1)") == Apply("scale", (Input(), Const(-1, INT)))


def test_negative_components_in_an_offset_literal() -> None:
    assert _elab("translate(input, (-1, 0))") == Apply(
        "translate", (Input(), Const(Offset(-1, 0), OFFSET))
    )


def test_boolean_literals_are_lowercase() -> None:
    program = _elab("flip_h(input) if true else input")
    assert isinstance(program, If)
    assert program.cond == Const(True, BOOL)
    with pytest.raises(LadderFormatError, match="write `true`, not `True`"):
        _elab("flip_h(input) if True else input")


def test_conditional_becomes_a_short_circuiting_if_node() -> None:
    program = _elab("map_color(input, 1, 2) if eq(most_common_color(input), 0) else input")
    assert program == If(
        cond=Apply("eq", (Apply("most_common_color", (Input(),)), Const(0, COLOR))),
        then=Apply("map_color", (Input(), Const(1, COLOR), Const(2, COLOR))),
        orelse=Input(),
    )


def test_conditional_over_a_floor_without_the_if_summoner_is_a_load_error() -> None:
    """Branching needs the `if` summoner in the floor or the engine never enumerates the branch.
    That coherence check lives at load (raised here), not in `lint()` -- so a branch is unreachable
    only if the ladder does not load at all."""
    no_if = Library(name="no-if", primitives=tuple(p for p in _LIB.primitives if p.name != "if"))
    with pytest.raises(LadderFormatError, match=r"needs the `if` summoner"):
        elaborate_expression("flip_h(input) if true else input", library=no_if, allow_input=True)
    # ... and it is exactly the summoner that is missing: with `if` present the same text loads.
    assert isinstance(_elab("flip_h(input) if true else input"), If)


def test_bare_primitive_in_a_function_position_is_a_primref() -> None:
    assert _elab("map(flip_h, gs)", (("gs", _GRIDS),)) == Apply(
        "map", (PrimRef("flip_h"), Param(0, _GRIDS))
    )


def test_bare_primitive_elsewhere_still_errors() -> None:
    # `flip_v` fills a Grid position, not a function one, so it stays an error.
    with pytest.raises(LadderFormatError, match=r"write `flip_v\(...\)` to apply it"):
        _elab("flip_h(flip_v)")


def test_lambda_takes_its_binder_types_from_the_position() -> None:
    """`build_grid`'s hole is curried `(int) -> (int) -> color`, so two binders peel two arrows;
    the innermost binder is De Bruijn 0."""
    program = _elab("build_grid(height(input), width(input), lambda r, c: read(input, c, r))")
    assert program == Apply(
        "build_grid",
        (
            Apply("height", (Input(),)),
            Apply("width", (Input(),)),
            Lam(INT, Lam(INT, Apply("read", (Input(), Var(0, INT), Var(1, INT))))),
        ),
    )


def test_applying_a_function_valued_parameter_is_an_appfn() -> None:
    program = _elab("f(g)", (("g", GRID), ("f", _GRID_FN)))
    assert program == AppFn(Param(1, _GRID_FN), (Param(0, GRID),))


@pytest.mark.parametrize(
    ("text", "params", "fragment"),
    [
        ("lambda r: read(input, r, r)", (), "only appears in a function-typed"),
        ("map(lambda a, b: a, gs)", (("gs", _GRIDS),), "no function type to take it from"),
        ("g(input)", (("g", GRID),), "is not a function"),
        ("build_grid(1, 1, lambda input, c: 0)", (), "reserved word"),
        ("map(flip_h, input)", (), "expected List"),
        ("flip_h(input) if input else input", (), "condition is Grid"),
    ],
)
def test_higher_order_errors(
    text: str, params: tuple[tuple[str, Type], ...], fragment: str
) -> None:
    with pytest.raises(LadderFormatError, match=fragment):
        _elab(text, params)


def test_a_binder_may_not_shadow_a_parameter() -> None:
    with pytest.raises(LadderFormatError, match="shadows a parameter"):
        elaborate_expression(
            "build_grid(1, 1, lambda r, c: read(g, r, c))",
            library=_LIB,
            params=(("g", GRID), ("r", INT)),
            allow_input=False,
        )


@pytest.mark.parametrize(
    ("text", "params"),
    [
        ("translate(input, (-1, 0))", ()),
        ("scale(input, -1)", ()),
        ("flip_h(input) if true else input", ()),
        ("map(flip_h, gs)", (("gs", _GRIDS),)),
        ("build_grid(height(input), width(input), lambda r, c: read(input, c, r))", ()),
        ("build_grid(height(input), width(input), lambda r, c: read(input, add(r, c), c))", ()),
        ("map_color(input, 1, 2) if eq(most_common_color(input), 0) else input", ()),
        ("f(g)", (("g", GRID), ("f", _GRID_FN))),
        ("map(f, gs)", (("gs", _GRIDS), ("f", _GRID_FN))),
    ],
)
def test_every_construct_round_trips(text: str, params: tuple[tuple[str, Type], ...]) -> None:
    """Binder names are arbitrary, so the fixed point is the PROGRAM, not the text."""
    program = _elab(text, params)
    names = tuple(name for name, _ in params)
    assert _elab(render_expression(program, names), params) == program


def test_binder_types_are_resolved_by_the_body() -> None:
    """`map`'s hole is `(a) -> b`, so a binder's type is a type VARIABLE when it is bound and is
    only pinned by what the body does with it. A stored program must carry the resolved type."""
    program = _elab("map(lambda x: flip_h(x), gs)", (("gs", _GRIDS),))
    assert isinstance(program, Apply)
    lam = program.args[0]
    assert isinstance(lam, Lam)
    assert lam.param_type == GRID  # not an unresolved `t0`
    assert lam.body == Apply("flip_h", (Var(0, GRID),))
