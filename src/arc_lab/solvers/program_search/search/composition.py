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


def first_order_applications(
    primitive: Primitive,
    candidates: Sequence[TypedProgram],
    counter: itertools.count[int],
) -> Iterator[TypedProgram]:
    """Every well-typed application of ``primitive``'s fixed parameters over ``candidates``.

    ``counter`` supplies fresh type-variable names (share one across an enumeration round so distinct
    polymorphic uses stay distinct). Parameters are filled left-to-right with early pruning: a
    candidate whose type fails to unify with the current parameter is skipped before the rest of the
    argument tuple is chosen, so ill-typed combinations are never fully built.
    """
    signature = instantiate(ArrowType(primitive.param_types, primitive.return_type), counter)
    assert isinstance(signature, ArrowType)  # instantiate preserves an ArrowType's shape
    params, result = signature.params, signature.result

    def fill(
        index: int, subst: Substitution, chosen: tuple[Program, ...]
    ) -> Iterator[TypedProgram]:
        if index == len(params):
            yield Apply(primitive=primitive.name, args=chosen), apply_subst(subst, result)
            return
        for program, ptype in candidates:
            threaded = unify(params[index], ptype, subst)
            if threaded is not None:
                yield from fill(index + 1, threaded, (*chosen, program))

    yield from fill(0, {}, ())
