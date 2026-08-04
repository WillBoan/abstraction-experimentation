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
from collections.abc import Callable, Iterator, Sequence
from typing import TypeAlias

from ..substrate.library import Primitive
from ..substrate.program import AppFn, Apply, Program
from ..substrate.types import ArrowType, Substitution, Type, apply_subst, instantiate, unify

#: A pooled program paired with its (instantiated) type — an argument candidate for composition.
TypedProgram: TypeAlias = "tuple[Program, Type]"

#: How a filled argument tuple becomes a program node (an ``Apply`` of a primitive, or an ``AppFn``
#: of a pooled function value).
_Build: TypeAlias = "Callable[[tuple[Program, ...]], Program]"


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
    yield from _fill(_apply_builder(primitive.name), packed.params, packed.result, candidates)


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
    build = _apply_builder(primitive.name)
    # Only the TAIL is order-invariant when declared so; the fixed leading parameters never are.
    canonical_from = len(fixed) if primitive.variadic_commutative else None
    for arity in range(1, max_arity + 1):
        parameters = (*fixed, *(variadic for _ in range(arity)))
        yield from _fill(
            build, parameters, packed.result, candidates, canonical_from=canonical_from
        )


def appfn_applications(
    candidates: Sequence[TypedProgram],
    counter: itertools.count[int],
) -> Iterator[TypedProgram]:
    """Apply each pooled function value to pooled arguments (§8) — the ``AppFn`` composition step.

    A candidate receives its (fresh-instantiated) arrow's parameters: an uncurried primitive value gets
    all its arguments at once; a curried value gets one currying step, its result possibly a further
    function value that is applied again in a later round.
    """
    for fn_program, fn_type in candidates:
        if not isinstance(fn_type, ArrowType):
            continue
        fresh = instantiate(fn_type, counter)
        assert isinstance(fresh, ArrowType)
        yield from _fill(_appfn_builder(fn_program), fresh.params, fresh.result, candidates)


def hole_assignments(
    primitive: Primitive,
    hole_index: int,
    candidates: Sequence[TypedProgram],
    counter: itertools.count[int],
) -> Iterator[tuple[tuple[Program, ...], Type, Type]]:
    """Every well-typed choice of ``primitive``'s parameters *other than* ``hole_index``, threading
    one substitution — used by lambda synthesis (§5.3) to pin a function-hole's type variables from
    sibling arguments that share them (e.g. ``map``'s hole ``a→b`` shares ``a`` with its ``List[a]``
    sibling).

    Yields the chosen sibling programs (parameter order, ``hole_index`` excluded), the hole's type
    *after* substitution, and the primitive's *return* type after the same substitution (``map``'s
    hole and its ``List[b]`` return type share ``b`` — both need the identical substitution applied,
    not just the hole). Each is fully resolved if every one of its free variables also appears in a
    filled parameter, still carrying free variables otherwise (the caller decides what to do with
    those, §6.2-style).

    A separate, smaller function rather than a generalized ``_fill``: unlike ``_fill``, this never
    builds a finished program (the hole isn't filled from the pool — it's synthesized by the caller
    afterward) and skips one parameter entirely rather than filling every one.
    """
    packed = instantiate(ArrowType(primitive.param_types, primitive.return_type), counter)
    assert isinstance(packed, ArrowType)
    sibling_positions = [i for i in range(len(packed.params)) if i != hole_index]

    def recurse(
        remaining: tuple[int, ...], subst: Substitution, chosen: dict[int, Program]
    ) -> Iterator[tuple[tuple[Program, ...], Type, Type]]:
        if not remaining:
            hole_type = apply_subst(subst, packed.params[hole_index])
            return_type = apply_subst(subst, packed.result)
            yield tuple(chosen[i] for i in sibling_positions), hole_type, return_type
            return
        index, rest = remaining[0], remaining[1:]
        for program, ptype in candidates:
            threaded = unify(packed.params[index], ptype, subst)
            if threaded is not None:
                yield from recurse(rest, threaded, {**chosen, index: program})

    yield from recurse(tuple(sibling_positions), {}, {})


def _apply_builder(name: str) -> _Build:
    return lambda args: Apply(primitive=name, args=args)


def _appfn_builder(function: Program) -> _Build:
    return lambda args: AppFn(fn=function, args=args)


def _fill(
    build: _Build,
    parameters: tuple[Type, ...],
    result: Type,
    candidates: Sequence[TypedProgram],
    *,
    canonical_from: int | None = None,
) -> Iterator[TypedProgram]:
    """Fill ``parameters`` left-to-right from ``candidates``, threading one substitution.

    A candidate whose type fails to unify with the current parameter is skipped before the rest of the
    argument tuple is chosen, so ill-typed combinations are never fully built. ``build`` turns a
    completed argument tuple into the program node (an ``Apply`` or an ``AppFn``).

    ``canonical_from`` marks the first index of an order-invariant run of parameters (a
    :attr:`~...library.Primitive.variadic_commutative` tail): from there on, candidates are drawn in
    non-decreasing index order, so the run is enumerated as combinations-with-replacement rather than
    as ordered tuples. Same *set* of argument multisets, ``k!`` fewer candidates built and counted.
    """

    def recurse(
        index: int, subst: Substitution, chosen: tuple[Program, ...], start: int
    ) -> Iterator[TypedProgram]:
        if index == len(parameters):
            yield build(chosen), apply_subst(subst, result)
            return
        canonical = canonical_from is not None and index >= canonical_from
        for offset in range(start if canonical else 0, len(candidates)):
            program, ptype = candidates[offset]
            threaded = unify(parameters[index], ptype, subst)
            if threaded is not None:
                # The ordering constraint applies only WITHIN the canonical run. A fixed leading
                # parameter draws from the same candidate list, so threading its offset into the
                # first tail slot would wrongly skip every earlier candidate there.
                yield from recurse(index + 1, threaded, (*chosen, program), offset if canonical else 0)

    yield from recurse(0, {}, (), 0)
