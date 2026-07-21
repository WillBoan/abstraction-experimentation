"""Type/signature surface syntax (LADDER-FORMAT.md FLR-8, RNG-2)."""

from __future__ import annotations

import pytest

from arc_lab.program_search.ladders.lang import (
    LadderFormatError,
    PrimitiveSignature,
    parse_definition_header,
    parse_primitive_signature,
    parse_type,
    render_primitive_signature,
    render_type,
)
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import (
    COLOR,
    GRID,
    INT,
    MASK,
    ArrowType,
    TypeVar,
    list_type,
    pair_type,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Grid", GRID),
        ("Color", COLOR),
        ("Int", INT),
        ("Mask", MASK),
        ("List[Grid]", list_type(GRID)),
        ("Pair[Grid, Color]", pair_type(GRID, COLOR)),
        ("List[Pair[Grid, Grid]]", list_type(pair_type(GRID, GRID))),
        ("a", TypeVar("a")),
        ("(Grid) -> Grid", ArrowType((GRID,), GRID)),
        ("(Grid, Int, Int) -> Color", ArrowType((GRID, INT, INT), COLOR)),
        ("() -> Grid", ArrowType((), GRID)),
    ],
)
def test_types_round_trip_through_their_canonical_spelling(text: str, expected: object) -> None:
    assert parse_type(text) == expected
    assert render_type(parse_type(text)) == text


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("grid", "capitalised"),  # the base type, miscased
        ("GRID", "capitalised"),
        ("Griid", "unknown type"),
        ("List", "1 type argument"),
        ("Pair[Grid]", "2 type argument"),
        ("Grid[Color]", "takes no type arguments"),
        ("Grid Color", "trailing"),
        ("(Grid)", "needs `->`"),
        ("(Grid -> Grid", "unclosed"),
        ("Grid ->", "trailing"),
        ("(Grid) ->", "unexpected end"),
    ],
)
def test_malformed_types_are_rejected(text: str, fragment: str) -> None:
    with pytest.raises(LadderFormatError, match=fragment):
        parse_type(text)


def test_variadic_signature_round_trips() -> None:
    signature = parse_primitive_signature("(Color, Grid...) -> Grid")
    assert signature == PrimitiveSignature(
        param_types=(COLOR,), return_type=GRID, variadic_param=GRID
    )
    assert render_primitive_signature(signature) == "(Color, Grid...) -> Grid"


def test_declared_signatures_match_the_substrate_registry() -> None:
    """FLR-7 is only enforceable because the two spellings agree -- checked here on every
    primitive any ladder floor uses, ``overlay`` (variadic) included."""
    for name in ("flip_h", "map_color", "overlay", "read", "set_cell", "crop_to_mask"):
        prim = BASE_PRIMITIVES[name]
        expected = PrimitiveSignature(
            param_types=prim.param_types,
            return_type=prim.return_type,
            variadic_param=prim.variadic_param,
        )
        text = render_primitive_signature(expected)
        assert parse_primitive_signature(text) == expected


def test_definition_header_carries_params_in_index_order() -> None:
    header = parse_definition_header("mirror_recolor(g: Grid, src: Color, dst: Color) -> Grid")
    assert header.name == "mirror_recolor"
    assert header.params == (("g", GRID), ("src", COLOR), ("dst", COLOR))
    assert header.param_types == (GRID, COLOR, COLOR)
    assert header.return_type == GRID


def test_definition_header_rejects_duplicate_param_names() -> None:
    with pytest.raises(LadderFormatError, match="duplicate parameter names"):
        parse_definition_header("f(g: Grid, g: Grid) -> Grid")


def test_definition_header_requires_type_annotations() -> None:
    with pytest.raises(LadderFormatError, match="needs a `: Type` annotation"):
        parse_definition_header("f(g) -> Grid")


@pytest.mark.parametrize(
    ("header", "fragment"),
    [
        ("f(input: Grid) -> Grid", "reserved word"),  # spec LEX-6
        ("f(train: Grid) -> Grid", "reserved word"),
        ("top(g: Grid) -> Grid", "reserved word"),
        ("f(from: Grid) -> Grid", "Python keyword"),  # spec NAM-1
        ("f(class: Grid) -> Grid", "Python keyword"),
        ("match(g: Grid) -> Grid", "Python keyword"),  # a soft keyword still confuses `ast`
    ],
)
def test_reserved_and_keyword_names_are_rejected(header: str, fragment: str) -> None:
    with pytest.raises(LadderFormatError, match=fragment):
        parse_definition_header(header)
