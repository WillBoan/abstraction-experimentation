"""The polymorphism-instantiation policy (§6.2): resolve, canonicalize, monotype universe."""

from __future__ import annotations

from arc_lab.program_search.search.polymorphism import (
    PolymorphismInstantiation,
    canonicalize,
    monotype_universe,
    resolve,
)
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.program import Input
from arc_lab.program_search.substrate.types import (
    GRID,
    INT,
    ArrowType,
    TypeVar,
    list_type,
)

_PROG = Input()
_ALL: tuple[PolymorphismInstantiation, ...] = ("monomorphize", "bounded", "unrestricted")


# -- resolve -------------------------------------------------------------------


def test_concrete_result_passes_through_every_policy() -> None:
    for policy in _ALL:
        assert list(resolve(_PROG, GRID, policy, ())) == [(_PROG, GRID)]


def test_monomorphize_rejects_a_free_var_result() -> None:
    assert list(resolve(_PROG, list_type(TypeVar("a")), "monomorphize", ())) == []


def test_unrestricted_keeps_a_canonicalized_polymorphic_entry() -> None:
    poly = ArrowType((TypeVar("a"),), TypeVar("a"))
    assert list(resolve(_PROG, poly, "unrestricted", ())) == [
        (_PROG, ArrowType((TypeVar("t0"),), TypeVar("t0")))
    ]


def test_bounded_grounds_free_vars_over_the_universe() -> None:
    result = list(resolve(_PROG, list_type(TypeVar("a")), "bounded", (GRID, INT)))
    assert (_PROG, list_type(GRID)) in result
    assert (_PROG, list_type(INT)) in result
    assert len(result) == 2


# -- canonicalize --------------------------------------------------------------


def test_canonicalize_makes_alpha_equivalent_polytypes_equal() -> None:
    aa = ArrowType((TypeVar("a"),), TypeVar("a"))
    bb = ArrowType((TypeVar("b"),), TypeVar("b"))
    canonical = ArrowType((TypeVar("t0"),), TypeVar("t0"))
    assert canonicalize(aa) == canonicalize(bb) == canonical


def test_canonicalize_distinguishes_distinct_vars_and_recurses() -> None:
    assert canonicalize(ArrowType((TypeVar("a"),), TypeVar("b"))) == ArrowType(
        (TypeVar("t0"),), TypeVar("t1")
    )
    assert canonicalize(list_type(TypeVar("x"))) == list_type(TypeVar("t0"))


def test_canonicalize_leaves_concrete_types_unchanged() -> None:
    assert canonicalize(list_type(GRID)) == list_type(GRID)


# -- monotype_universe ---------------------------------------------------------


def test_universe_of_a_monomorphic_library_is_its_return_types() -> None:
    library = Library(
        name="m",
        primitives=(
            Primitive(name="a", param_types=(GRID,), return_type=GRID, impl=lambda g: g),
            Primitive(name="b", param_types=(GRID,), return_type=INT, impl=lambda g: 0),
        ),
    )
    assert set(monotype_universe(library, max_depth=3)) == {GRID, INT}


def test_universe_closes_under_present_constructors() -> None:
    library = Library(
        name="l",
        primitives=(
            Primitive(
                name="wrap", param_types=(GRID,), return_type=list_type(GRID), impl=lambda g: (g,)
            ),
        ),
    )
    universe = set(monotype_universe(library, max_depth=2))
    assert list_type(GRID) in universe  # the seed return type
    assert list_type(list_type(GRID)) in universe  # one level of constructor closure
