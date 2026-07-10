"""Partial signatures (the ``⊥`` sentinel) and the runtime type check ``signature_matches_type``."""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.solvers.program_search.search.context import Context
from arc_lab.solvers.program_search.search.signature import (
    BOTTOM,
    compute_signature,
    is_total,
    signature_matches_type,
)
from arc_lab.solvers.program_search.substrate.library import Library, Primitive
from arc_lab.solvers.program_search.substrate.program import Input, Var
from arc_lab.solvers.program_search.substrate.types import (
    BOOL,
    COLOR,
    FN,
    GRID,
    INT,
    ArrowType,
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
    assert BOTTOM != 0
    assert BOTTOM != ()
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
