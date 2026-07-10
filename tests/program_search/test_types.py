"""The type system: TypeCon unification, parametric containers, and serialization.

Two obligations. **Regression:** a nullary ``TypeCon`` (base type) must behave byte-identically to the
old atomic ``BaseType`` — same unify/instantiate/substitute/serialize results — so folding base types
into the constructor changed nothing for first-order code. **New:** parametric constructors
(``list``/``pair``) unify argument-wise, respect arity, and round-trip.
"""

from __future__ import annotations

import itertools

import pytest

from arc_lab.solvers.program_search.substrate.types import (
    BOOL,
    COLOR,
    GRID,
    INT,
    ArrowType,
    TypeCon,
    TypeVar,
    apply_subst,
    base_type,
    free_type_vars,
    instantiate,
    list_type,
    pair_type,
    type_from_serializable,
    type_to_serializable,
    unify,
)

# -- Regression: nullary TypeCon behaves exactly as the old BaseType ------------


def test_base_types_are_nullary_constructors() -> None:
    assert TypeCon("grid") == GRID
    assert GRID.args == ()
    assert str(GRID) == "grid"


def test_base_unify_same_succeeds_empty() -> None:
    assert unify(GRID, GRID) == {}


def test_base_unify_distinct_fails() -> None:
    assert unify(GRID, INT) is None
    assert unify(BOOL, COLOR) is None


def test_typevar_binds_to_base() -> None:
    a = TypeVar("a")
    assert unify(a, GRID) == {"a": GRID}
    assert unify(GRID, a) == {"a": GRID}


def test_base_instantiate_and_substitute_are_identity() -> None:
    assert instantiate(GRID, itertools.count()) == GRID
    assert apply_subst({"a": INT}, GRID) == GRID
    assert free_type_vars(GRID) == set()


def test_base_serializes_to_bare_string() -> None:
    assert type_to_serializable(GRID) == "grid"
    assert type_from_serializable("grid") == GRID
    assert type_from_serializable(type_to_serializable(COLOR)) == COLOR


def test_base_type_lookup_is_fail_fast() -> None:
    assert base_type("int") is INT
    with pytest.raises(ValueError, match="unknown base type"):
        base_type("nope")


# -- New: parametric constructors ----------------------------------------------


def test_parametric_unify_binds_argument() -> None:
    a = TypeVar("a")
    assert unify(list_type(a), list_type(INT)) == {"a": INT}


def test_parametric_unify_distinct_arguments_fail() -> None:
    assert unify(list_type(INT), list_type(COLOR)) is None


def test_pair_unifies_pointwise() -> None:
    a, b = TypeVar("a"), TypeVar("b")
    assert unify(pair_type(a, b), pair_type(INT, COLOR)) == {"a": INT, "b": COLOR}


def test_constructor_name_and_arity_must_match() -> None:
    # different constructor name
    assert unify(list_type(INT), pair_type(INT, INT)) is None
    # same name, different arity
    assert unify(TypeCon("list", (INT,)), TypeCon("list", (INT, INT))) is None


def test_occurs_check_rejects_infinite_type() -> None:
    a = TypeVar("a")
    assert unify(a, list_type(a)) is None


def test_free_type_vars_recurse_into_args() -> None:
    a, b = TypeVar("a"), TypeVar("b")
    assert free_type_vars(list_type(a)) == {"a"}
    assert free_type_vars(pair_type(a, list_type(b))) == {"a", "b"}


def test_substitute_recurses_into_args() -> None:
    a = TypeVar("a")
    assert apply_subst({"a": INT}, list_type(a)) == list_type(INT)


def test_instantiate_renames_nested_vars_freshly() -> None:
    a = TypeVar("a")
    fresh = instantiate(list_type(a), itertools.count())
    assert isinstance(fresh, TypeCon)
    assert fresh.name == "list"
    (inner,) = fresh.args
    assert isinstance(inner, TypeVar)
    assert inner.name != "a"  # renamed to a fresh name


def test_parametric_serialization_round_trips() -> None:
    nested = pair_type(INT, list_type(COLOR))
    data = type_to_serializable(nested)
    assert data == {"con": "pair", "args": ["int", {"con": "list", "args": ["color"]}]}
    assert type_from_serializable(data) == nested


def test_parametric_str() -> None:
    assert str(list_type(INT)) == "list[int]"
    assert str(pair_type(INT, COLOR)) == "pair[int, color]"


# -- Regression: arrow types unchanged -----------------------------------------


def test_arrow_unifies_arity_and_pointwise() -> None:
    a, b = TypeVar("a"), TypeVar("b")
    assert unify(ArrowType((a,), b), ArrowType((INT,), COLOR)) == {"a": INT, "b": COLOR}
    assert unify(ArrowType((INT, INT), COLOR), ArrowType((INT,), COLOR)) is None


def test_arrow_serialization_round_trips() -> None:
    arrow = ArrowType((INT, INT), COLOR)
    assert type_from_serializable(type_to_serializable(arrow)) == arrow
