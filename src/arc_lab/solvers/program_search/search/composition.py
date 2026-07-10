"""Composition: generating well-typed applications from the pool (§5.2 of ARCHITECTURE.md).

The first-order core: for a primitive, instantiate its (possibly polymorphic) signature with fresh
type variables, unify each parameter against a pooled argument's type threading one ``Substitution``,
and read the instantiated result type back out with ``apply_subst``. The **type flows out of
composition** — every generated program is paired with its type (which the pool then keys on), so a
program's type is never recomputed after the fact.

Variadic trailing arguments (§5.2), higher-order function holes (§5.3), and short-circuit ``If``
(§5.4) layer on top of this core in later steps; this module handles a primitive's *fixed* parameters.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator, Sequence
from typing import TypeAlias

from ..substrate.library import Primitive
from ..substrate.program import Apply, Program
from ..substrate.types import ArrowType, Substitution, Type, apply_subst, instantiate, unify

#: A pooled program paired with its (instantiated) type — an argument candidate for composition.
TypedProgram: TypeAlias = "tuple[Program, Type]"


def applications(
    primitive: Primitive,
    candidates: Sequence[TypedProgram],
    counter: itertools.count[int],
    max_arity: int,
) -> Iterator[TypedProgram]:
    """Every well-typed application of ``primitive`` over ``candidates`` — variadic-aware.

    A variadic primitive is enumerated at each arity ``1 … max_arity`` of its trailing argument; a
    fixed-arity primitive ignores ``max_arity``. This is the dispatcher the engine calls per primitive.
    """
    if primitive.is_variadic:
        return variadic_applications(primitive, candidates, counter, max_arity)
    return first_order_applications(primitive, candidates, counter)


def first_order_applications(
    primitive: Primitive,
    candidates: Sequence[TypedProgram],
    counter: itertools.count[int],
) -> Iterator[TypedProgram]:
    """Every well-typed application of ``primitive``'s fixed parameters over ``candidates``.

    ``counter`` supplies fresh type-variable names (share one across an enumeration round so distinct
    polymorphic uses stay distinct).
    """
    packed = instantiate(ArrowType(primitive.param_types, primitive.return_type), counter)
    assert isinstance(packed, ArrowType)  # instantiate preserves an ArrowType's shape
    yield from _fill(primitive.name, packed.params, packed.result, candidates)


def variadic_applications(
    primitive: Primitive,
    candidates: Sequence[TypedProgram],
    counter: itertools.count[int],
    max_arity: int,
) -> Iterator[TypedProgram]:
    """Applications of a variadic ``primitive`` at each trailing arity ``1 … max_arity``.

    The trailing arguments share the single variadic element type (so if it is polymorphic they all
    unify to one type); ``max_arity`` bounds the fan-out. The fixed leading parameters are filled first.
    """
    assert primitive.variadic_param is not None  # guaranteed by ``is_variadic``
    packed = instantiate(
        ArrowType((*primitive.param_types, primitive.variadic_param), primitive.return_type),
        counter,
    )
    assert isinstance(packed, ArrowType)
    *fixed, variadic = packed.params
    for arity in range(1, max_arity + 1):
        parameters = (*fixed, *(variadic for _ in range(arity)))
        yield from _fill(primitive.name, parameters, packed.result, candidates)


def _fill(
    name: str,
    parameters: tuple[Type, ...],
    result: Type,
    candidates: Sequence[TypedProgram],
) -> Iterator[TypedProgram]:
    """Fill ``parameters`` left-to-right from ``candidates``, threading one substitution.

    A candidate whose type fails to unify with the current parameter is skipped before the rest of the
    argument tuple is chosen, so ill-typed combinations are never fully built.
    """

    def recurse(
        index: int, subst: Substitution, chosen: tuple[Program, ...]
    ) -> Iterator[TypedProgram]:
        if index == len(parameters):
            yield Apply(primitive=name, args=chosen), apply_subst(subst, result)
            return
        for program, ptype in candidates:
            threaded = unify(parameters[index], ptype, subst)
            if threaded is not None:
                yield from recurse(index + 1, threaded, (*chosen, program))

    yield from recurse(0, {}, ())
