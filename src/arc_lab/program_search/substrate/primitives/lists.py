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


def _nth(xs: Value, index: int) -> Value:
    """The ``index``-th element, 0-based. Out of range raises, like ``head`` of an empty list.

    ``head`` alone could only ever reach the first element, so "the nth thing" -- a common enough
    percept that cfb2ce5a's floor hard-coded two of them -- was inexpressible.
    """
    if not isinstance(xs, tuple):
        raise TypeError(f"nth expects a list, got {type(xs).__name__}")
    if index < 0 or index >= len(xs):
        raise ValueError(f"index {index} out of range for a list of {len(xs)}")
    return xs[index]


def _range(count: int) -> Value:
    """``0 .. count - 1``. The one thing that turns a *number* into a list.

    Nothing else in the substrate produces a list from anything but a grid's contents (``cells`` /
    ``palette``), so without this ``map``/``fold`` had nothing index-shaped to range over.
    """
    if count < 0:
        raise ValueError(f"range count must be non-negative, got {count}")
    return tuple(range(count))


ZIP = Primitive(
    name="zip",
    param_types=(list_type(_A), list_type(_B)),
    return_type=list_type(pair_type(_A, _B)),
    impl=_zip,
)
LENGTH = Primitive(name="length", param_types=(list_type(_A),), return_type=INT, impl=_length)
HEAD = Primitive(name="head", param_types=(list_type(_A),), return_type=_A, impl=_head)
NTH = Primitive(name="nth", param_types=(list_type(_A), INT), return_type=_A, impl=_nth)
RANGE = Primitive(name="range", param_types=(INT,), return_type=list_type(INT), impl=_range)

LIST_PRIMITIVES = (ZIP, LENGTH, HEAD, NTH, RANGE)
