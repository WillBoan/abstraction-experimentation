"""Tests for the polymorphic type language: Hindley-Milner unification + serialization."""

from __future__ import annotations

import itertools

from arc_lab.solvers.dsl.substrate.types import (
    ArrowType,
    TypeVar,
    ValueType,
    apply_subst,
    instantiate,
    type_from_serializable,
    type_to_serializable,
    unify,
)

_G, _C, _I = ValueType.GRID, ValueType.COLOR, ValueType.INT


def test_unify_base_types() -> None:
    assert unify(_G, _G) == {}
    assert unify(_G, _I) is None  # distinct base types never unify


def test_unify_binds_a_variable_either_way() -> None:
    a = TypeVar("a")
    assert unify(a, _G) == {"a": _G}
    assert unify(_G, a) == {"a": _G}  # symmetric
    assert apply_subst({"a": _G}, a) == _G


def test_unify_arrows_pointwise_and_by_arity() -> None:
    f = ArrowType((_G,), _I)  # GRID -> INT (a perceiver)
    assert unify(f, ArrowType((_G,), _I)) == {}
    assert unify(f, ArrowType((_G,), _C)) is None  # result mismatch
    assert unify(f, ArrowType((_G, _G), _I)) is None  # arity mismatch


def test_unify_a_polymorphic_signature_against_concrete_args() -> None:
    # apply : ((a -> b), a) -> b  applied to a GRID->INT perceiver and a GRID  =>  result must be INT.
    a, b, r = TypeVar("a"), TypeVar("b"), TypeVar("r")
    apply_sig = ArrowType((ArrowType((a,), b), a), b)
    call = ArrowType((ArrowType((_G,), _I), _G), r)
    subst = unify(apply_sig, call)
    assert subst is not None
    assert apply_subst(subst, b) == _I  # b inferred = INT
    assert apply_subst(subst, r) == _I  # the call's result unified through to INT


def test_occurs_check_rejects_infinite_types() -> None:
    a = TypeVar("a")
    assert unify(a, ArrowType((a,), _I)) is None  # a = (a) -> INT has no finite solution


def test_instantiate_gives_fresh_variables_each_use() -> None:
    sig = ArrowType((TypeVar("a"),), TypeVar("a"))  # a -> a (identity)
    counter = itertools.count()
    first, second = instantiate(sig, counter), instantiate(sig, counter)
    assert first != second  # distinct uses get distinct fresh variables
    assert isinstance(first, ArrowType)
    assert first.params[0] == first.result  # the a -> a shape is preserved within a use


def test_serialization_round_trips_and_base_types_stay_bare_strings() -> None:
    assert type_to_serializable(_G) == "grid"  # backward-compatible with every committed artifact
    for t in (
        _G,
        _I,
        TypeVar("a"),
        ArrowType((_G, _I), _C),
        ArrowType((ArrowType((_G,), _I),), _G),  # nested (a perceiver in a hole)
    ):
        assert type_from_serializable(type_to_serializable(t)) == t
