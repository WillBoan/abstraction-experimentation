"""The polymorphism-instantiation policy (§6.2 of ARCHITECTURE.md).

After composition (§5.2) unifies a primitive's fresh signature against pooled arguments, the result
type may still carry a **free type variable** — a var unconstrained by the arguments (e.g. an
empty-list constructor ``() -> list[a]``). This policy governs that residue:

- ``monomorphize`` (the default): reject the candidate — the pool stays concrete-only.
- ``bounded``: ground each free var over the task-reachable monotype universe (the library's var-free
  return types, closed under the type constructors present, to ``max_depth`` nestings), enumerating
  each grounding.
- ``unrestricted``: keep a polymorphic entry, its type key **canonicalized** (free vars renamed in
  first-occurrence order) so alpha-equivalent polytypes share one key. Such entries are re-instantiated
  with fresh vars when consumed as arguments (done by the engine, once per round).
"""

from __future__ import annotations

import itertools
from collections.abc import Iterator, Sequence
from typing import Literal, TypeAlias

from ..substrate.library import Library
from ..substrate.program import Program
from ..substrate.types import (
    ArrowType,
    Type,
    TypeCon,
    TypeVar,
    apply_subst,
    free_type_vars,
)

PolymorphismInstantiation: TypeAlias = Literal["monomorphize", "bounded", "unrestricted"]


def resolve(
    program: Program,
    result_type: Type,
    policy: PolymorphismInstantiation,
    universe: Sequence[Type],
) -> Iterator[tuple[Program, Type]]:
    """Apply the policy to one composed candidate, yielding 0+ concrete-or-canonical typed programs.

    A candidate whose result type is already concrete passes through unchanged under every policy.
    """
    free = free_type_vars(result_type)
    if not free:
        yield program, result_type
        return
    if policy == "monomorphize":
        return
    if policy == "unrestricted":
        yield program, canonicalize(result_type)
        return
    ordered = sorted(free)  # deterministic grounding order
    for grounding in itertools.product(universe, repeat=len(ordered)):
        subst = dict(zip(ordered, grounding, strict=True))
        yield program, apply_subst(subst, result_type)


def canonicalize(t: Type) -> Type:
    """Rename free type vars in first-occurrence order (``t0``, ``t1``, …).

    So alpha-equivalent polytypes (``a -> a`` and ``b -> b``) share one representation, hence one pool
    key. On consumption the engine re-instantiates the entry with fresh vars, so these names never clash.
    """
    mapping: dict[str, TypeVar] = {}

    def rename(node: Type) -> Type:
        if isinstance(node, TypeVar):
            if node.name not in mapping:
                mapping[node.name] = TypeVar(f"t{len(mapping)}")
            return mapping[node.name]
        if isinstance(node, TypeCon):
            if not node.args:
                return node
            return TypeCon(node.name, tuple(rename(arg) for arg in node.args))
        return ArrowType(tuple(rename(param) for param in node.params), rename(node.result))

    return rename(t)


def monotype_universe(library: Library, max_depth: int) -> tuple[Type, ...]:
    """The monotypes ``bounded`` grounds over: the library's var-free return types, closed under the
    type constructors present in the library, to ``max_depth`` nestings."""
    universe: set[Type] = {
        primitive.return_type
        for primitive in library.primitives
        if not free_type_vars(primitive.return_type)
    }
    constructors = _present_constructors(library)
    for _ in range(max_depth):
        grown = set(universe)
        for name, arity in constructors:
            if arity == 0:
                continue  # a nullary constructor is a base type — already a candidate seed
            for args in itertools.product(universe, repeat=arity):
                grown.add(TypeCon(name, args))
        if grown == universe:
            break
        universe = grown
    return tuple(sorted(universe, key=str))


def _present_constructors(library: Library) -> set[tuple[str, int]]:
    """Every ``(name, arity)`` type constructor appearing anywhere in the library's types."""
    found: set[tuple[str, int]] = set()

    def walk(t: Type) -> None:
        if isinstance(t, TypeCon):
            found.add((t.name, len(t.args)))
            for arg in t.args:
                walk(arg)
        elif isinstance(t, ArrowType):
            for param in t.params:
                walk(param)
            walk(t.result)

    for primitive in library.primitives:
        for param in primitive.param_types:
            walk(param)
        walk(primitive.return_type)
        if primitive.variadic_param is not None:
            walk(primitive.variadic_param)
    return found
