"""Expression elaboration text <-> ``Program`` (LADDER-FORMAT.md EXP-1..7).

The load-bearing test is :func:`test_every_batch_template_round_trips`: the surface language must
express every rung template and top solution the 20 committed ladders already use, or the format
cannot be their source of truth.
"""

from __future__ import annotations

import pytest

from arc_lab.program_search.ladders.lang import (
    LadderFormatError,
    elaborate_expression,
    render_expression,
)
from arc_lab.program_search.ladders.registry import LADDERS
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.color import MAP_COLOR
from arc_lab.program_search.substrate.primitives.combinators import OVERLAY
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.program import Apply, Const, Input, Param, Program
from arc_lab.program_search.substrate.types import COLOR, GRID, Type

_FLOOR = Library(
    name="test-floor",
    primitives=(D4_LIBRARY.get("flip_h"), D4_LIBRARY.get("flip_v"), MAP_COLOR),
)
_OVERLAY = Library(name="test-overlay", primitives=(OVERLAY, D4_LIBRARY.get("flip_h")))


def _elaborate(
    text: str, *, params: tuple[tuple[str, Type], ...] = (), library: Library = _FLOOR
) -> Program:
    return elaborate_expression(text, library=library, params=params, allow_input=True)


def test_template_elaborates_to_the_committed_program() -> None:
    """al1's ``mirror_recolor``, written in the surface syntax, is the registry module's tree."""
    program = elaborate_expression(
        "map_color(flip_h(flip_v(g)), src, dst)",
        library=_FLOOR,
        params=(("g", GRID), ("src", COLOR), ("dst", COLOR)),
        allow_input=False,
    )
    assert program == Apply(
        "map_color",
        (
            Apply("flip_h", (Apply("flip_v", (Param(0, GRID),)),)),
            Param(1, COLOR),
            Param(2, COLOR),
        ),
    )


def test_int_literals_take_the_type_of_their_argument_position() -> None:
    program = _elaborate("map_color(input, 1, 2)")
    assert program == Apply("map_color", (Input(), Const(1, COLOR), Const(2, COLOR)))


def test_variadic_primitive_accepts_extra_arguments() -> None:
    """al13's ``sym_h`` -- ``overlay`` is ``(Color, Grid...) -> Grid``."""
    program = elaborate_expression(
        "overlay(c, g, flip_h(g))",
        library=_OVERLAY,
        params=(("g", GRID), ("c", COLOR)),
        allow_input=False,
    )
    assert program == Apply(
        "overlay", (Param(1, COLOR), Param(0, GRID), Apply("flip_h", (Param(0, GRID),)))
    )


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("flip_h(g, g)", "takes 1 argument"),
        ("flip_h()", "takes 1 argument"),
        ("map_color(input, 1)", "takes 3 argument"),
        ("flip_h(1)", "cannot fill a `Grid` position"),
        ("map_color(1, 1, 1)", "cannot fill a `Grid` position"),
        ("rot180(input)", "unknown function"),
        ("flip_h(x)", "unknown name"),
        ("flip_h", "write `flip_h\\(...\\)`"),
        ("1", "an int literal only appears in a typed argument position"),
        ("flip_h(-1)", "unary operator"),
        ("flip_h(input) + flip_v(input)", "arithmetic operator"),
        ("map_color(input, from=1, to=2)", "could not parse"),
        ("flip_h([[1, 2]])", "list literal"),
        ("flip_h(lambda g: g)", "lambda"),
        ("flip_h(*args)", "`\\*` argument"),
        ("map_color(input, True, 2)", "unsupported literal"),
        ("map_color(input, 1.5, 2)", "unsupported literal"),
        ("", "empty expression"),
    ],
)
def test_out_of_fragment_expressions_are_rejected(text: str, fragment: str) -> None:
    with pytest.raises(LadderFormatError, match=fragment):
        _elaborate(text)


def test_input_is_out_of_scope_in_a_closed_template() -> None:
    with pytest.raises(LadderFormatError, match="not in scope"):
        elaborate_expression(
            "flip_h(input)", library=_FLOOR, params=(("g", GRID),), allow_input=False
        )


def test_a_parameter_cannot_be_applied() -> None:
    with pytest.raises(LadderFormatError, match="is a parameter, not a function"):
        elaborate_expression("g(input)", library=_FLOOR, params=(("g", GRID),), allow_input=False)


def test_every_batch_template_round_trips() -> None:
    """Every rung template and top solution in the committed batch survives
    ``render -> elaborate`` unchanged: the surface language covers the batch (spec EXP-7)."""
    checked = 0
    for name, build in LADDERS.items():
        spec = build()
        for level, rung in enumerate(spec.rungs, start=1):
            library = spec.oracle_library(level - 1)
            # The minted primitive's param_types are the template's hole types, in index order.
            param_types = spec.oracle_library(level).get(rung.name).param_types
            names = tuple(f"p{index}" for index in range(len(param_types)))
            params = tuple(zip(names, param_types, strict=True))
            text = render_expression(rung.template, names)
            elaborated = elaborate_expression(
                text, library=library, params=params, allow_input=False
            )
            assert elaborated == rung.template, (
                f"{name} r{level} ({rung.name}) did not round-trip: {text}"
            )
            checked += 1
        top_library = spec.oracle_library(len(spec.rungs))
        for solution in spec.top.reference_solutions:
            text = render_expression(solution)
            assert (
                elaborate_expression(text, library=top_library, params=(), allow_input=True)
                == solution
            ), f"{name} top did not round-trip: {text}"
            checked += 1
    assert checked >= 60  # 20 ladders x (rungs + top solutions)
