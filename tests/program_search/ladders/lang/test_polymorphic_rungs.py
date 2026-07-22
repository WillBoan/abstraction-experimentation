"""Rungs over polymorphic combinators (LADDER-FORMAT.md RNG-2, EXP-6).

`Program.result_type` reports a primitive's DECLARED return type without unification, so a template
rooted at `map`/`filter`/`head`/... derives a free type variable and could never mint usably. The
author states the signature, elaboration verifies it by unification, and `make_abstraction` is told
what to mint -- these tests pin all three halves.
"""

from __future__ import annotations

import pytest

from arc_lab.program_search.ladders.lang.expr import elaborate_typed
from arc_lab.program_search.ladders.lang.type_syntax import parse_definition_header
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import BOOL, GRID, Type, list_type, unify

_LIB = Library(
    name="poly",
    primitives=tuple(
        BASE_PRIMITIVES[n] for n in ("map", "filter", "length", "head", "eq", "flip_h", "flip_v")
    ),
)


def _mint(line: str) -> tuple[tuple[Type, ...], Type]:
    left, _, body = line.partition("=")
    header = parse_definition_header(left.strip())
    template, actual = elaborate_typed(
        body.strip(), library=_LIB, params=header.params, allow_input=False
    )
    assert unify(actual, header.return_type) is not None, (actual, header.return_type)
    prim = make_abstraction(
        header.name, template, _LIB, signature=(header.param_types, header.return_type)
    )
    return prim.param_types, prim.return_type


def test_a_rung_rooted_at_map_mints_its_declared_type() -> None:
    _, return_type = _mint("flip_all(gs: List[Grid]) -> List[Grid] = map(flip_h, gs)")
    assert return_type == list_type(GRID)  # not the raw `list[b]` the substrate would derive


def test_shared_type_variables_express_corresponding_types() -> None:
    """The `a` repeated across the list and the function is the CONSTRAINT that they match."""
    params, return_type = _mint("custom_map(l: List[a], f: (a) -> Bool) -> List[Bool] = map(f, l)")
    assert return_type == list_type(BOOL)
    assert len(params) == 2


@pytest.mark.parametrize("var", ["a", "t", "elem"])
def test_the_authors_choice_of_variable_name_does_not_matter(var: str) -> None:
    """Before the signature fix this passed only when the name happened to match the substrate's."""
    _, return_type = _mint(
        f"first_matching(l: List[{var}], f: ({var}) -> Bool) -> {var} = head(filter(f, l))"
    )
    assert str(return_type) == var


def test_a_wrong_return_type_is_still_rejected() -> None:
    """Trusting the declaration must not disable the check -- unification still has to hold."""
    with pytest.raises(AssertionError):
        _mint("wrong(gs: List[Grid]) -> Grid = map(flip_h, gs)")


def test_signature_arity_must_match_the_template() -> None:
    """The one thing a declaration cannot fake: the parameter count comes from the Param nodes."""
    header = parse_definition_header("unused(gs: List[Grid], x: Grid) -> List[Grid]")
    template, _ = elaborate_typed(
        "map(flip_h, gs)", library=_LIB, params=header.params, allow_input=False
    )
    with pytest.raises(ValueError, match="signature declares 2 parameter"):
        make_abstraction(
            "unused", template, _LIB, signature=(header.param_types, header.return_type)
        )
