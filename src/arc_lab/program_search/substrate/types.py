"""The type system: type constructors, function types, and type variables.

Programs pass *values* between primitives, and every value has a type. A :data:`Type` is one of:

* a :class:`TypeCon` — a **type constructor** ``name[a1, …, an]`` applied to ``n`` type arguments.
  Atomic base types are the **nullary** case (``GRID = TypeCon("grid")``); containers are parametric
  (``list[a]``, ``pair[a, b]``). One uniform mechanism covers both — a base type is just a constructor
  that takes no arguments.
* an :class:`ArrowType` — a **function type** ``(p1, …, pn) -> r`` (n-ary, matching a primitive's
  multi-argument signature). It is what lets typed enumeration target a function-valued hole precisely
  (e.g. a ``(int, int) -> color`` cell body), rather than an opaque function tag.
* a :class:`TypeVar` — a **type variable**, for polymorphism (``map : ((a -> b), list[a]) -> list[b]``).

All three are frozen dataclasses — inspectable, hashable data. Types are what make search over a large,
atomic vocabulary tractable: typed enumeration only ever composes type-compatible pieces (unified — see
:func:`unify`), pruning the otherwise-explosive space before a program is ever evaluated.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import TypeAlias


@dataclass(frozen=True, slots=True)
class TypeCon:
    """A type constructor applied to type arguments — ``name[args…]``.

    The nullary case (``args == ()``) is an atomic base type: :data:`GRID`, :data:`INT`, and friends.
    Parametric constructors carry their arguments: ``list[a]`` is ``TypeCon("list", (a,))``.
    """

    name: str
    args: tuple[Type, ...] = ()

    def __str__(self) -> str:
        if not self.args:
            return self.name
        return f"{self.name}[{', '.join(str(a) for a in self.args)}]"


@dataclass(frozen=True, slots=True)
class TypeVar:
    """A type variable — a hole in a polymorphic signature (e.g. the ``a`` in ``list[a] -> a``)."""

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


#: A type: a (possibly parametric) constructor, a function type, or a type variable.
Type: TypeAlias = "TypeCon | ArrowType | TypeVar"

#: A unifier: a mapping from :class:`TypeVar` names to the types they stand for.
Substitution: TypeAlias = "dict[str, Type]"

#: The atomic base types — nullary constructors, held as singletons.
GRID = TypeCon("grid")
COLOR = TypeCon("color")  # a cell color, integer 0-9
INT = TypeCon("int")  # a small non-negative integer (e.g. a tiling dimension)
BOOL = TypeCon("bool")  # a truth value, produced by control primitives and branch conditions
FN = TypeCon("fn")  # an opaque function value; an ArrowType refines it where the shape is known

_BASE_TYPES: dict[str, TypeCon] = {t.name: t for t in (GRID, COLOR, INT, BOOL, FN)}


def list_type(element: Type) -> TypeCon:
    """The list constructor ``list[element]``."""
    return TypeCon("list", (element,))


def pair_type(first: Type, second: Type) -> TypeCon:
    """The pair constructor ``pair[first, second]``."""
    return TypeCon("pair", (first, second))


def base_type(name: str) -> TypeCon:
    """The nullary base-type singleton for ``name``; raises :class:`ValueError` for an unknown name.

    This is the deserialization boundary for bare-string types, so it is deliberately fail-fast — a
    typo'd or truncated type tag must be rejected loudly. A new base type is added by registering a
    singleton in :data:`_BASE_TYPES`, so strictness never blocks a legitimate type.
    """
    try:
        return _BASE_TYPES[name]
    except KeyError:
        raise ValueError(f"unknown base type {name!r}") from None


def free_type_vars(t: Type) -> set[str]:
    """The names of the type variables occurring in ``t``."""
    if isinstance(t, TypeVar):
        return {t.name}
    if isinstance(t, TypeCon):
        names: set[str] = set()
        for arg in t.args:
            names |= free_type_vars(arg)
        return names
    names = set()
    for param in t.params:
        names |= free_type_vars(param)
    return names | free_type_vars(t.result)


def apply_subst(subst: Substitution, t: Type) -> Type:
    """Substitute bound type variables throughout ``t`` (chasing through the mapping)."""
    if isinstance(t, TypeVar):
        return apply_subst(subst, subst[t.name]) if t.name in subst else t
    if isinstance(t, TypeCon):
        if not t.args:
            return t
        return TypeCon(t.name, tuple(apply_subst(subst, a) for a in t.args))
    return ArrowType(tuple(apply_subst(subst, p) for p in t.params), apply_subst(subst, t.result))


def unify(t1: Type, t2: Type, subst: Substitution | None = None) -> Substitution | None:
    """Hindley-Milner unification: the substitution making ``t1`` == ``t2``, or ``None`` if none exists.

    A :class:`TypeVar` binds to any type (with an occurs-check to reject infinite types);
    :class:`TypeCon`\\ s unify iff their names and arities match, then argument-wise; :class:`ArrowType`\\ s
    unify arity-wise and pointwise. Nullary constructors (base types) unify iff they are the same name —
    the loop over zero arguments is a no-op — so base-type behaviour is the natural special case.
    """
    subst = {} if subst is None else subst
    a, b = apply_subst(subst, t1), apply_subst(subst, t2)
    if isinstance(a, TypeVar):
        return _bind(a.name, b, subst)
    if isinstance(b, TypeVar):
        return _bind(b.name, a, subst)
    if isinstance(a, TypeCon) and isinstance(b, TypeCon):
        if a.name != b.name or len(a.args) != len(b.args):
            return None
        current: Substitution | None = subst
        for xa, xb in zip(a.args, b.args, strict=True):
            current = unify(xa, xb, current)
            if current is None:
                return None
        return current
    if isinstance(a, ArrowType) and isinstance(b, ArrowType):
        if len(a.params) != len(b.params):
            return None
        current = subst
        for pa, pb in zip(a.params, b.params, strict=True):
            current = unify(pa, pb, current)
            if current is None:
                return None
        return unify(a.result, b.result, current)
    return None


def _bind(name: str, t: Type, subst: Substitution) -> Substitution | None:
    if isinstance(t, TypeVar) and t.name == name:
        return subst
    if name in free_type_vars(t):  # occurs-check: reject `a = list[a]`-style infinite types
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
        if isinstance(node, TypeCon):
            if not node.args:
                return node
            return TypeCon(node.name, tuple(fresh(a) for a in node.args))
        return ArrowType(tuple(fresh(p) for p in node.params), fresh(node.result))

    return fresh(t)


#: A serialized type: a bare string (nullary base type) or a tagged dict (constructor / arrow / variable).
Serialized: TypeAlias = "str | dict[str, object]"


def type_to_serializable(t: Type) -> Serialized:
    """Serialize a type — a nullary base type to its bare string, everything else to a tagged dict."""
    if isinstance(t, TypeVar):
        return {"var": t.name}
    if isinstance(t, ArrowType):
        return {
            "arrow": [type_to_serializable(p) for p in t.params],
            "result": type_to_serializable(t.result),
        }
    if not t.args:
        return t.name
    return {"con": t.name, "args": [type_to_serializable(a) for a in t.args]}


def type_from_serializable(data: Serialized) -> Type:
    """Reconstruct a type from :func:`type_to_serializable` (a bare string is a nullary base type)."""
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
    if "con" in data:
        name, args = data["con"], data["args"]
        if not isinstance(name, str) or not isinstance(args, list):
            raise ValueError(f"malformed type constructor: {data!r}")
        return TypeCon(name, tuple(type_from_serializable(_serialized(a)) for a in args))
    raise ValueError(f"unknown serialized type: {data!r}")


def _serialized(value: object) -> Serialized:
    if isinstance(value, (str, dict)):
        return value
    raise ValueError(f"malformed serialized type fragment: {value!r}")
