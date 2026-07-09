"""Shared type-directed composition helpers for search strategies.

Both the closed-term enumerator and the open-term ``build_grid`` body search need the same core
machinery: instantiate a primitive signature once, thread a unifier across its arguments, and derive
the instantiated return type from the final substitution. Keeping that logic in one place means the
search stack learns first-order polymorphism (e.g. ``eq`` / ``if``) uniformly rather than via local
special-cases.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator, Sequence
from typing import TypeAlias

from arc_lab.core.grid import Grid
from arc_lab.solvers.dsl.substrate.library import Closure, Primitive, Value
from arc_lab.solvers.dsl.substrate.program import Program
from arc_lab.solvers.dsl.substrate.types import (
    BOOL,
    COLOR,
    FN,
    GRID,
    INT,
    ArrowType,
    Type,
    TypeVar,
    apply_subst,
    instantiate,
    unify,
)

TypedProgram: TypeAlias = "tuple[Program, Type]"


def candidate_applications(
    prim: Primitive,
    *,
    value_candidates: Sequence[TypedProgram],
    function_candidates: Sequence[TypedProgram] = (),
    result_targets: Sequence[Type] | None = None,
) -> Iterator[tuple[tuple[Program, ...], Type]]:
    """Every well-typed argument tuple for ``prim``, plus the instantiated result type.

    ``result_targets`` seeds the primitive's instantiated return type before argument selection.
    That keeps polymorphic-return primitives goal-directed when the caller already knows which
    result type is useful (e.g. a ``build_grid`` body whose root must be ``COLOR``), while leaving
    the closed enumerator free to explore the full first-order space by omitting it.
    """

    signature = instantiate(ArrowType(tuple(prim.param_types), prim.return_type), itertools.count())
    assert isinstance(signature, ArrowType)

    exact_value_candidates: dict[Type, tuple[TypedProgram, ...]] = {}
    first_order_candidates: list[TypedProgram] = []
    for candidate in value_candidates:
        exact_value_candidates[candidate[1]] = (
            *exact_value_candidates.get(candidate[1], ()),
            candidate,
        )
        if not isinstance(candidate[1], ArrowType) and candidate[1] != FN:
            first_order_candidates.append(candidate)

    def sources(param_type: Type) -> Sequence[TypedProgram]:
        if isinstance(param_type, ArrowType):
            return function_candidates
        if isinstance(param_type, TypeVar):
            return first_order_candidates
        return exact_value_candidates.get(param_type, ())

    def backtrack(
        index: int,
        subst: dict[str, Type],
        chosen: list[Program],
    ) -> Iterator[tuple[tuple[Program, ...], Type]]:
        if index == len(signature.params):
            yield tuple(chosen), apply_subst(subst, signature.result)
            return
        param_type = apply_subst(subst, signature.params[index])
        for program, result_type in sources(param_type):
            next_subst = unify(param_type, result_type, subst)
            if next_subst is None:
                continue
            chosen.append(program)
            yield from backtrack(index + 1, next_subst, chosen)
            chosen.pop()

    initial_subst = _seed_subst(signature.result, result_targets)
    if initial_subst is None:
        return
    yield from backtrack(0, initial_subst, [])


def _seed_subst(result_type: Type, result_targets: Sequence[Type] | None) -> dict[str, Type] | None:
    """Initial substitution for a primitive application.

    When a caller provides exactly one desired result type, bind the primitive's instantiated
    return against it before any arguments are chosen. Multiple targets are handled by the caller
    by invoking :func:`candidate_applications` separately per target, so this helper stays single-
    purpose and deterministic.
    """
    if result_targets is None:
        return {}
    if len(result_targets) != 1:
        raise ValueError("candidate_applications accepts at most one result target per call")
    subst = unify(result_type, result_targets[0], {})
    return subst


def signature_matches_type(signature: tuple[Value, ...], expected: Type) -> bool:
    """Whether every runtime value in ``signature`` matches the declared DSL type ``expected``."""

    if isinstance(expected, TypeVar):
        return False
    if isinstance(expected, ArrowType):
        return all(_is_function_value(value) for value in signature)
    if expected == GRID:
        return all(isinstance(value, Grid) for value in signature)
    if expected == BOOL:
        return all(isinstance(value, bool) for value in signature)
    if expected in (INT, COLOR):
        return all(isinstance(value, int) and not isinstance(value, bool) for value in signature)
    if expected == FN:
        return all(_is_function_value(value) for value in signature)
    return False


def _is_function_value(value: Value) -> bool:
    return isinstance(value, (Closure, Primitive))
