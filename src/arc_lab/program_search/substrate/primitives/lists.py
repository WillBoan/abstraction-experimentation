"""First-order list vocabulary (ONTOLOGY.md L0): no function holes, plain structural operations.

``zip`` is *strict* — a length mismatch raises rather than silently truncating, so a mismatched
composition prunes as ``⊥`` instead of producing a plausible-but-wrong value. ``head`` on an empty
list raises for the same reason. (The higher-order list operations — ``map``/``filter``/``fold``/
``sort_by`` — live in ``higher_order.py``; these are their hole-free structural companions.)
"""

from __future__ import annotations

from arc_lab.program_search.substrate.library import Primitive, Value
from arc_lab.program_search.substrate.types import INT, TypeVar, list_type, pair_type

_A = TypeVar("a")
_B = TypeVar("b")


def _zip(xs: Value, ys: Value) -> Value:
    if not isinstance(xs, tuple) or not isinstance(ys, tuple):
        raise TypeError("zip expects two lists")
    if len(xs) != len(ys):
        raise ValueError(f"zip requires equal lengths, got {len(xs)} and {len(ys)}")
    return tuple(zip(xs, ys, strict=True))


def _length(xs: Value) -> int:
    if not isinstance(xs, tuple):
        raise TypeError(f"length expects a list, got {type(xs).__name__}")
    return len(xs)


def _head(xs: Value) -> Value:
    if not isinstance(xs, tuple):
        raise TypeError(f"head expects a list, got {type(xs).__name__}")
    if not xs:
        raise ValueError("head of an empty list")
    return xs[0]


ZIP = Primitive(
    name="zip",
    param_types=(list_type(_A), list_type(_B)),
    return_type=list_type(pair_type(_A, _B)),
    impl=_zip,
)
LENGTH = Primitive(name="length", param_types=(list_type(_A),), return_type=INT, impl=_length)
HEAD = Primitive(name="head", param_types=(list_type(_A),), return_type=_A, impl=_head)

LIST_PRIMITIVES = (ZIP, LENGTH, HEAD)
