"""The DSL type system: atomic base types, function types, and type variables.

Programs pass *values* between primitives, and every value has a type. A :data:`Type` is one of:

* a :class:`BaseType` — an **atomic base type** (:data:`GRID`, :data:`COLOR`, :data:`INT`, and the
  opaque function tag :data:`FN`). These are the leaves — module-level singletons, the closed set the
  vocabulary uses today (new base types slot in as more constants). Existing first-order code is typed
  entirely in these.
* an :class:`ArrowType` — a **function type** ``(p1, …, pn) -> r`` (n-ary, matching a primitive's
  multi-argument signature). Refines the opaque ``FN`` tag: it is what lets typed enumeration target a
  function-valued hole precisely (e.g. a ``GRID -> INT`` perceiver), the higher-order unlock.
* a :class:`TypeVar` — a **type variable**, for polymorphism (``map : ((a -> b), [a]) -> [b]``).

All three are frozen dataclasses — one uniform mechanism — so a type is inspectable, hashable data.
Types are what make search over a larger, more atomic vocabulary tractable: typed enumeration only ever
composes type-compatible pieces (unified — see :func:`unify`), pruning the otherwise-explosive space
before a program is ever evaluated. Base types serialize to their bare string name (backward-compatible
with every committed artifact); composite types serialize to a small tagged dict.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class BaseType:
    """An atomic base type — a leaf of :data:`Type`."""

    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class TypeVar:
    """A type variable — a hole in a polymorphic signature (e.g. the ``a`` in ``[a] -> a``)."""

    name: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class ArrowType:
    """A function type ``(params…) -> result`` — n-ary, matching a primitive's argument list."""

    params: tuple[Type, ...]
    result: Type

    def __str__(self) -> str:
        args = ", ".join(str(p) for p in self.params)
        return f"({args}) -> {self.result}"


#: A type in the DSL: an atomic base type, a function type, or a type variable.
Type: TypeAlias = "BaseType | ArrowType | TypeVar"

#: A unifier: a mapping from :class:`TypeVar` names to the types they stand for.
Substitution: TypeAlias = "dict[str, Type]"

#: The base-type singletons. New base types (mask, object, …) slot in as more of these.
GRID = BaseType("grid")
COLOR = BaseType("color")  # a cell color, integer 0-9
INT = BaseType("int")  # a small non-negative integer (e.g. a tiling dimension)
FN = BaseType("fn")  # an opaque function value (a lambda's closure); ArrowType refines it

_BASE_TYPES: dict[str, BaseType] = {t.name: t for t in (GRID, COLOR, INT, FN)}


def base_type(name: str) -> BaseType:
    """The base-type singleton for ``name`` (or a fresh :class:`BaseType` for an unknown name)."""
    return _BASE_TYPES.get(name, BaseType(name))


def free_type_vars(t: Type) -> set[str]:
    """The names of the type variables occurring in ``t``."""
    if isinstance(t, TypeVar):
        return {t.name}
    if isinstance(t, ArrowType):
        names: set[str] = set()
        for param in t.params:
            names |= free_type_vars(param)
        return names | free_type_vars(t.result)
    return set()


def apply_subst(subst: Substitution, t: Type) -> Type:
    """Substitute bound type variables throughout ``t`` (chasing through the mapping)."""
    if isinstance(t, TypeVar):
        return apply_subst(subst, subst[t.name]) if t.name in subst else t
    if isinstance(t, ArrowType):
        return ArrowType(
            tuple(apply_subst(subst, p) for p in t.params), apply_subst(subst, t.result)
        )
    return t


def unify(t1: Type, t2: Type, subst: Substitution | None = None) -> Substitution | None:
    """Hindley-Milner unification: the substitution making ``t1`` == ``t2``, or ``None`` if none exists.

    Base types unify only with themselves; a :class:`TypeVar` binds to any type (with an occurs-check
    to reject infinite types); :class:`ArrowType`\\ s unify arity-wise and pointwise. Returned
    substitutions compose, so this is the type-directed filter a higher-order enumeration prunes with.
    """
    subst = {} if subst is None else subst
    a, b = apply_subst(subst, t1), apply_subst(subst, t2)
    if isinstance(a, TypeVar):
        return _bind(a.name, b, subst)
    if isinstance(b, TypeVar):
        return _bind(b.name, a, subst)
    if isinstance(a, BaseType) and isinstance(b, BaseType):
        return subst if a == b else None
    if isinstance(a, ArrowType) and isinstance(b, ArrowType):
        if len(a.params) != len(b.params):
            return None
        current: Substitution | None = subst
        for pa, pb in zip(a.params, b.params, strict=True):
            current = unify(pa, pb, current)
            if current is None:
                return None
        return unify(a.result, b.result, current)
    return None


def _bind(name: str, t: Type, subst: Substitution) -> Substitution | None:
    if isinstance(t, TypeVar) and t.name == name:
        return subst
    if name in free_type_vars(t):  # occurs-check: reject `a = [a]`-style infinite types
        return None
    return {**subst, name: t}


def instantiate(t: Type, counter: itertools.count[int]) -> Type:
    """A fresh copy of ``t`` with every type variable renamed uniquely (per use of a polymorphic sig).

    ``counter`` supplies the fresh names deterministically (no RNG — reproducibility is load-bearing);
    pass one ``itertools.count()`` across a whole enumeration round so distinct uses stay distinct.
    """
    mapping: dict[str, TypeVar] = {}

    def fresh(node: Type) -> Type:
        if isinstance(node, TypeVar):
            if node.name not in mapping:
                mapping[node.name] = TypeVar(f"t{next(counter)}")
            return mapping[node.name]
        if isinstance(node, ArrowType):
            return ArrowType(tuple(fresh(p) for p in node.params), fresh(node.result))
        return node

    return fresh(t)


#: A serialized type: a bare string (base type) or a tagged dict (arrow / variable).
Serialized: TypeAlias = "str | dict[str, object]"


def type_to_serializable(t: Type) -> Serialized:
    """Serialize a type — a base type to its bare string (backward-compatible), else a tagged dict."""
    if isinstance(t, BaseType):
        return t.name
    if isinstance(t, TypeVar):
        return {"var": t.name}
    return {
        "arrow": [type_to_serializable(p) for p in t.params],
        "result": type_to_serializable(t.result),
    }


def type_from_serializable(data: Serialized) -> Type:
    """Reconstruct a type from :func:`type_to_serializable` (a bare string is a base type)."""
    if isinstance(data, str):
        return base_type(data)
    if "var" in data:
        name = data["var"]
        if not isinstance(name, str):
            raise ValueError(f"malformed type variable: {data!r}")
        return TypeVar(name)
    if "arrow" in data:
        params, result = data["arrow"], data["result"]
        if not isinstance(params, list):
            raise ValueError(f"malformed arrow type: {data!r}")
        return ArrowType(
            tuple(type_from_serializable(_serialized(p)) for p in params),
            type_from_serializable(_serialized(result)),
        )
    raise ValueError(f"unknown serialized type: {data!r}")


def _serialized(value: object) -> Serialized:
    if isinstance(value, (str, dict)):
        return value
    raise ValueError(f"malformed serialized type fragment: {value!r}")
