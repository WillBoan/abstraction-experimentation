"""Program signatures: partial behavioural fingerprints, and the runtime type check.

A :data:`Signature` is a program's *behaviour* — the value it produces at each evaluation context.
It is **partial**: a context where the program errors (an out-of-bounds ``read``, a type error) is
recorded as :data:`BOTTOM` (``⊥``) rather than discarding the program. Partial programs stay in the
pool because they are the branch scaffolding an ``if`` composes into a total program — a branch may
legitimately be undefined outside the domain where it is selected.

Two programs are observationally equivalent iff their signatures are equal (``⊥`` included), and a
program *solves* a target iff its signature :func:`is_total` and equals the target.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from enum import Enum
from typing import TypeAlias

from arc_lab.core.grid import Grid

from ..substrate.library import Closure, Library, Primitive, Value, apply_function_value
from ..substrate.program import Program
from ..substrate.types import ArrowType, Type, TypeVar
from .context import Context


class Bottom(Enum):
    """The ``⊥`` of a partial signature: a context where the program errored."""

    BOTTOM = "⊥"

    def __str__(self) -> str:
        return "⊥"


#: The singleton ``⊥``. ``BOTTOM is BOTTOM`` and ``BOTTOM != v`` for every concrete value ``v``, so
#: partial behaviours dedup correctly and a partial program never matches a concrete target.
BOTTOM = Bottom.BOTTOM

#: A program's behaviour: its value at each context, or ``⊥`` where it errors.
Signature: TypeAlias = "tuple[Value | Bottom, ...]"


def is_total(signature: Signature) -> bool:
    """True if the program is defined at every context (no ``⊥``) — a prerequisite for a solution."""
    return BOTTOM not in signature


def compute_signature(
    program: Program, contexts: tuple[Context, ...], library: Library
) -> Signature | None:
    """A program's partial signature over ``contexts``: its value at each, ``⊥`` where it raises.

    Each context supplies the input grid and the runtime ``scope`` binding (``env`` stays empty —
    forward search binds no abstraction arguments). Returns ``None`` **only** if the program raises on
    *every* context (fully undefined); one that raises on only some contexts keeps a partial signature
    and stays pooled — that partiality is what makes domain-splitting ``if`` work.
    """
    values: list[Value | Bottom] = []
    any_defined = False
    for context in contexts:
        try:
            value = program.evaluate(context.input_grid, library, scope=context.scope_binding)
        except Exception:
            values.append(BOTTOM)
        else:
            values.append(value)
            any_defined = True
    return tuple(values) if any_defined else None


def peel_arrow(arrow_type: ArrowType) -> tuple[list[Type], Type]:
    """Flatten a (possibly curried) arrow into its ultimate parameter types and non-arrow result."""
    params: list[Type] = []
    current: Type = arrow_type
    while isinstance(current, ArrowType):
        params.extend(current.params)
        current = current.result
    return params, current


def compute_function_signature(
    function: Program,
    arrow_type: ArrowType,
    contexts: tuple[Context, ...],
    arg_samples: Mapping[Type, Sequence[Value]],
    library: Library,
) -> Signature | None:
    """A function value's behavioral signature: its result on sampled argument tuples, per context.

    The function is evaluated once per context (so input-dependent functions are captured), then
    applied — curried — to each argument tuple from the cartesian product of ``arg_samples`` at its
    (peeled) parameter types. ``⊥`` marks any application that raises; ``None`` iff the function is
    undefined everywhere. Bounded samples make this **sound** (the goal test verifies every assembled
    program) but complete only up to sample adequacy.
    """
    param_types, _ = peel_arrow(arrow_type)
    arg_tuples = list(itertools.product(*(tuple(arg_samples.get(p, ())) for p in param_types)))
    values: list[Value | Bottom] = []
    any_defined = False
    for context in contexts:
        try:
            fn_value: Value | None = function.evaluate(
                context.input_grid, library, scope=context.scope_binding
            )
        except Exception:
            fn_value = None
        for args in arg_tuples:
            if fn_value is None:
                values.append(BOTTOM)
                continue
            try:
                values.append(apply_function_value(fn_value, args))
                any_defined = True
            except Exception:
                values.append(BOTTOM)
    return tuple(values) if any_defined else None


def combine_if_signature(cond: Signature, then: Signature, orelse: Signature) -> Signature | None:
    """An ``If`` node's signature, combined from its parts' **cached** signatures (§5.4).

    Per context: ``⊥`` if the condition is ``⊥``, else the selected branch's cached value — which is
    inherently short-circuit (the unselected branch's entry is never read), so a branch that is
    ``⊥`` outside its selected region still contributes. This is what makes domain-splitting ``if``
    work, with no re-evaluation. Returns ``None`` iff the combination is undefined everywhere,
    mirroring :func:`compute_signature`.
    """
    values: list[Value | Bottom] = []
    any_defined = False
    for selector, when_true, when_false in zip(cond, then, orelse, strict=True):
        if selector is BOTTOM:
            values.append(BOTTOM)
            continue
        value = when_true if selector else when_false
        values.append(value)
        if value is not BOTTOM:
            any_defined = True
    return tuple(values) if any_defined else None


def signature_matches_type(signature: Signature, expected: Type) -> bool:
    """Whether every *defined* value in ``signature`` inhabits ``expected``.

    ``⊥`` entries are skipped: a partial program is type-consistent on the contexts where it is
    defined, and the type-mismatch prune must not reject it for the contexts it declines.
    """
    return all(_inhabits(value, expected) for value in signature if value is not BOTTOM)


def _inhabits(value: Value, expected: Type) -> bool:
    """Whether a single runtime ``value`` inhabits the type ``expected``."""
    if isinstance(expected, TypeVar):
        return False  # an unresolved type variable matches no concrete value
    if isinstance(expected, ArrowType):
        return _is_function(value)
    name, args = expected.name, expected.args
    if name == "grid":
        return isinstance(value, Grid)
    if name == "bool":
        return isinstance(value, bool)
    if name in ("int", "color"):
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "fn":
        return _is_function(value)
    if name == "list" and len(args) == 1:
        return isinstance(value, tuple) and all(_inhabits(element, args[0]) for element in value)
    if name == "pair" and len(args) == 2:
        return (
            isinstance(value, tuple)
            and len(value) == 2
            and _inhabits(value[0], args[0])
            and _inhabits(value[1], args[1])
        )
    return False


def _is_function(value: Value) -> bool:
    return isinstance(value, (Closure, Primitive))
