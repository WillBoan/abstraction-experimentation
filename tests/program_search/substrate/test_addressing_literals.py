"""`Const` carrying a Coord/Offset literal: both codecs, the ladder syntax, and the constant leaves.

**Why these are literals at all.** Without them a coordinate can only be built by *applying*
``coord``/``offset``, which costs a level of :func:`compositional_depth` at every call site:
``translate(g, 0, 1)`` would become ``translate(g, offset(0, 1))``, taking al15/al17's ``shift1``
rung from d_i=2 to d_i=3 — past the ``depth_limit: 2`` those ladders declare. As round-0 leaves the
depth profile is preserved exactly; ``test_a_ladder_writes_an_offset_as_a_tuple_literal_and_keeps_its_depth``
below is the assertion that pins it.
"""

from __future__ import annotations

import pytest

from arc_lab.core.geometry import Coord, Offset
from arc_lab.core.grid import Grid
from arc_lab.program_search.learn.stitch_shim import from_sexpr, to_sexpr
from arc_lab.program_search.search.leaves import policy_constants
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.program import Apply, Const, Program
from arc_lab.program_search.substrate.types import COORD, GRID, OFFSET

_LITERALS = [
    Const(Coord(1, 2), COORD),
    Const(Offset(0, 1), OFFSET),
    Const(Offset(-3, -4), OFFSET),  # negatives must survive the `a_b` s-expr encoding
    Const(Coord(0, 0), COORD),
]

#: A library that *uses* the addressing types, so `_type_in_use` lets their constants be minted.
_ADDRESSING_LIBRARY = Library(
    "addressing",
    (
        Primitive(name="at", param_types=(GRID, COORD), return_type=GRID, impl=lambda g, c: g),
        Primitive(name="by", param_types=(GRID, OFFSET), return_type=GRID, impl=lambda g, o: g),
    ),
)


@pytest.mark.parametrize("literal", _LITERALS)
def test_a_literal_round_trips_through_the_dict_codec(literal: Const) -> None:
    assert Program.from_dict(literal.to_dict()) == literal


@pytest.mark.parametrize("literal", _LITERALS)
def test_a_literal_round_trips_through_the_sexpr_codec(literal: Const) -> None:
    # One opaque terminal to Stitch (`0_1:offset`) — it must not render as `<0, 1>`, whose spaces
    # would tokenize as several atoms and corrupt the term.
    encoded = to_sexpr(literal)
    assert " " not in encoded and "<" not in encoded
    assert from_sexpr(encoded, _ADDRESSING_LIBRARY) == literal


@pytest.mark.parametrize(
    "data",
    [
        {"op": "const", "value": [1], "value_type": "coord"},  # too short
        {"op": "const", "value": [1, 2, 3], "value_type": "offset"},  # too long
        {"op": "const", "value": 5, "value_type": "coord"},  # not a pair at all
        {"op": "const", "value": [True, 2], "value_type": "coord"},  # bool is not a component
    ],
)
def test_a_malformed_literal_is_rejected_loudly(data: dict[str, object]) -> None:
    # Fail-fast like the scalar branches: a truncated pair must not silently become a different
    # coordinate.
    with pytest.raises(ValueError, match="malformed const node"):
        Program.from_dict(data)


def _minted(grids: list[Grid], source: str, library: Library, vtype: object) -> set[object]:
    """The literal values one constant policy mints at ``vtype`` for these grids."""
    return {
        program.value
        for program, minted_type in policy_constants(grids, (source,), library)  # type: ignore[arg-type]
        if minted_type == vtype and isinstance(program, Const)
    }


def test_finite_enumerate_mints_the_addressing_square_only_when_the_library_uses_it() -> None:
    grids = [Grid.from_list([[0, 0], [0, 0]])]  # max dimension 2 -> components 0..2
    library = _ADDRESSING_LIBRARY
    assert _minted(grids, "finite-enumerate", library, COORD) == {
        Coord(r, c) for r in range(3) for c in range(3)
    }
    assert _minted(grids, "finite-enumerate", library, OFFSET) == {
        Offset(r, c) for r in range(3) for c in range(3)
    }

    # A library with no addressing type in any signature mints none of them -- the existing
    # `_type_in_use` gate, which is what keeps the quadratic cost off every other search.
    d4_only = Library(
        "grid-only",
        (Primitive(name="id", param_types=(GRID,), return_type=GRID, impl=lambda g: g),),
    )
    assert not _minted(grids, "finite-enumerate", d4_only, COORD)
    assert not _minted(grids, "finite-enumerate", d4_only, OFFSET)


def test_harvest_from_instance_mints_the_cross_product_of_observed_dimensions() -> None:
    grids = [Grid.from_list([[0, 0, 0], [0, 0, 0]])]  # 2x3 -> dimensions {2, 3}
    assert _minted(grids, "harvest-from-instance", _ADDRESSING_LIBRARY, COORD) == {
        Coord(a, b) for a in (2, 3) for b in (2, 3)
    }


# -- the `.ladder` surface syntax -------------------------------------------------------------

_LADDER_LIBRARY = Library(
    "ladder",
    (
        Primitive(name="translate", param_types=(GRID, OFFSET), return_type=GRID, impl=len),
        Primitive(name="concat_v", param_types=(GRID, GRID), return_type=GRID, impl=len),
    ),
)


def _elaborated(text: str) -> Program:
    from arc_lab.program_search.ladders.lang.expr import elaborate_expression

    return elaborate_expression(text, library=_LADDER_LIBRARY, allow_input=True)


def test_a_ladder_writes_an_offset_as_a_tuple_literal_and_keeps_its_depth() -> None:
    """THE load-bearing assertion of the whole `Const` extension.

    al15/al17's `shift1` is `concat_v(g, translate(g, 0, 1))` at d_i=2 under `depth_limit: 2`.
    Spelling the offset as an application (`offset(0, 1)`) would make it d_i=3 and put the rung out
    of reach of its own budget. As a literal it stays at 2.
    """
    from arc_lab.program_search.analysis.depth import compositional_depth

    assert compositional_depth(_elaborated("translate(input, (0, 1))")) == 1
    assert compositional_depth(_elaborated("concat_v(input, translate(input, (0, 1)))")) == 2


def test_the_literal_takes_its_type_from_the_position_it_fills() -> None:
    # Same rule as an int literal (COLOR vs INT): context decides, so `(0, 1)` is unambiguous and
    # never competes with a structural `pair`.
    elaborated = _elaborated("translate(input, (-1, 2))")
    assert isinstance(elaborated, Apply)
    assert elaborated.args[1] == Const(Offset(-1, 2), OFFSET)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("translate(input, (0, 1, 2))", "exactly 2 components"),
        ("translate(input, (0, input))", "pair of int literals"),
        ("translate(input, (0, true))", "pair of int literals"),
    ],
)
def test_a_malformed_ladder_literal_is_a_load_error(text: str, message: str) -> None:
    from arc_lab.program_search.ladders.lang.errors import LadderFormatError

    with pytest.raises(LadderFormatError, match=message):
        _elaborated(text)
