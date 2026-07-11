"""Partial signatures (the ``⊥`` sentinel) and the runtime type check ``signature_matches_type``."""

from __future__ import annotations

from collections.abc import Sequence

from arc_lab.core.grid import Grid
from arc_lab.program_search.search.context import Context
from arc_lab.program_search.search.signature import (
    BOTTOM,
    Bottom,
    compute_function_signature,
    compute_signature,
    is_total,
    signature_matches_type,
)
from arc_lab.program_search.substrate.library import (
    Library,
    Primitive,
    Value,
    apply_function_value,
)
from arc_lab.program_search.substrate.program import Input, Lam, PrimRef, Var
from arc_lab.program_search.substrate.types import (
    BOOL,
    COLOR,
    FN,
    GRID,
    INT,
    ArrowType,
    Type,
    TypeVar,
    list_type,
    pair_type,
)

_GRID = Grid.from_list([[1, 2], [3, 4]])
_G2 = Grid.from_list([[5, 6], [7, 8]])
_FN = Primitive(name="id", param_types=(GRID,), return_type=GRID, impl=lambda g: g)
_EMPTY_LIB = Library(name="test", primitives=())


# -- the ⊥ sentinel & is_total -------------------------------------------------


def test_bottom_is_a_distinct_singleton() -> None:
    assert BOTTOM is BOTTOM
    zero: Value | Bottom = 0
    empty: Value | Bottom = ()
    assert zero != BOTTOM
    assert empty != BOTTOM
    assert str(BOTTOM) == "⊥"


def test_is_total() -> None:
    assert is_total((1, 2, 3))
    assert is_total(())  # vacuously total
    assert not is_total((1, BOTTOM, 3))


# -- scalar inhabitation -------------------------------------------------------


def test_int_and_color_accept_ints_reject_bools() -> None:
    assert signature_matches_type((1, 2), INT)
    assert signature_matches_type((1, 2), COLOR)
    assert not signature_matches_type((1, True), INT)


def test_bool_accepts_bools_only() -> None:
    assert signature_matches_type((True, False), BOOL)
    assert not signature_matches_type((True, 1), BOOL)


def test_grid_inhabitation() -> None:
    assert signature_matches_type((_GRID,), GRID)
    assert not signature_matches_type((1,), GRID)


# -- partial signatures: ⊥ is skipped -----------------------------------------


def test_bottom_entries_are_skipped() -> None:
    assert signature_matches_type((1, BOTTOM, 3), INT)  # defined parts all int
    assert not signature_matches_type((1, BOTTOM, True), INT)  # a defined part is a bool
    assert signature_matches_type((BOTTOM, BOTTOM), INT)  # nothing defined ⇒ vacuously true


# -- function values -----------------------------------------------------------


def test_function_value_matches_arrow_and_fn() -> None:
    assert signature_matches_type((_FN,), ArrowType((GRID,), GRID))
    assert signature_matches_type((_FN,), FN)
    assert not signature_matches_type((_FN,), GRID)
    assert not signature_matches_type((1,), ArrowType((GRID,), GRID))


# -- containers ----------------------------------------------------------------


def test_list_inhabitation() -> None:
    assert signature_matches_type(((1, 2, 3), ()), list_type(INT))  # tuples of ints; empty ok
    assert not signature_matches_type(((1, True),), list_type(INT))  # a bad element
    assert not signature_matches_type((1,), list_type(INT))  # not a tuple


def test_pair_inhabitation() -> None:
    assert signature_matches_type(((1, _GRID),), pair_type(INT, GRID))
    assert not signature_matches_type(((1, 2, 3),), pair_type(INT, INT))  # wrong arity
    assert not signature_matches_type(((1, True),), pair_type(INT, INT))  # bad second element


def test_nested_container() -> None:
    assert signature_matches_type((((1, 2), (3, 4)),), list_type(pair_type(INT, INT)))


# -- type variables ------------------------------------------------------------


def test_type_variable_matches_nothing_concrete() -> None:
    assert not signature_matches_type((1,), TypeVar("a"))


# -- compute_signature: partial evaluation over contexts -----------------------


def test_compute_signature_total() -> None:
    sig = compute_signature(Input(), (Context(_GRID), Context(_G2)), _EMPTY_LIB)
    assert sig == (_GRID, _G2)


def test_compute_signature_partial_marks_errors_bottom() -> None:
    var = Var(index=0, value_type=INT)  # reads scope[-1]; raises on an empty binding
    sig = compute_signature(var, (Context(_GRID, ()), Context(_GRID, (5,))), _EMPTY_LIB)
    assert sig == (BOTTOM, 5)


def test_compute_signature_fully_undefined_is_none() -> None:
    var = Var(index=0, value_type=INT)  # raises everywhere: no binding at any context
    assert compute_signature(var, (Context(_GRID, ()),), _EMPTY_LIB) is None


# -- function values: application semantics & behavioral signatures -------------


def test_apply_function_value_primitive_is_uncurried() -> None:
    inc = Primitive(name="inc", param_types=(INT,), return_type=INT, impl=lambda x: x + 1)
    assert apply_function_value(inc, (5,)) == 6


def test_apply_function_value_closure_is_curried() -> None:
    # a curried function returning its outer (row = $1) argument
    fn = Lam(param_type=INT, body=Lam(param_type=INT, body=Var(index=1, value_type=INT)))
    closure = fn.evaluate(_GRID, _EMPTY_LIB)
    assert apply_function_value(closure, (7, 9)) == 7


def test_function_signature_of_a_primref() -> None:
    inc = Primitive(name="inc", param_types=(INT,), return_type=INT, impl=lambda x: x + 1)
    library = Library(name="t", primitives=(inc,))
    samples: dict[Type, Sequence[Value]] = {INT: [0, 5]}
    sig = compute_function_signature(
        PrimRef(name="inc"), ArrowType((INT,), INT), (Context(_GRID),), samples, library
    )
    assert sig == (1, 6)  # inc(0), inc(5)


def test_function_signature_discriminates_by_behavior() -> None:
    arrow = ArrowType((INT,), ArrowType((INT,), INT))
    samples: dict[Type, Sequence[Value]] = {INT: [0, 1, 2]}
    col = Lam(param_type=INT, body=Lam(param_type=INT, body=Var(index=0, value_type=INT)))  # col
    row = Lam(param_type=INT, body=Lam(param_type=INT, body=Var(index=1, value_type=INT)))  # row
    sig_col = compute_function_signature(col, arrow, (Context(_GRID),), samples, _EMPTY_LIB)
    sig_row = compute_function_signature(row, arrow, (Context(_GRID),), samples, _EMPTY_LIB)
    assert sig_col != sig_row  # a sample with row != col separates them
    col_again = Lam(param_type=INT, body=Lam(param_type=INT, body=Var(index=0, value_type=INT)))
    assert (
        compute_function_signature(col_again, arrow, (Context(_GRID),), samples, _EMPTY_LIB)
        == sig_col
    )


def test_function_signature_none_when_undefined_everywhere() -> None:
    bad = Lam(param_type=INT, body=Var(index=5, value_type=INT))  # $5 out of scope → raises
    sig = compute_function_signature(
        bad, ArrowType((INT,), INT), (Context(_GRID),), {INT: [0]}, _EMPTY_LIB
    )
    assert sig is None
