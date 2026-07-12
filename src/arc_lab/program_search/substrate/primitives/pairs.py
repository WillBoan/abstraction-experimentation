"""Pair intro/elim (ONTOLOGY.md L0): the polymorphic product type's vocabulary.

The runtime representation is a plain 2-tuple (``library.py``'s ``Value`` contract: the type lives
on the program, not the value). ONTOLOGY's ``Coord`` is this at ``pair[int, int]`` — ``make_coord``
/ ``row`` / ``col`` are the monomorphic faces of ``pair`` / ``fst`` / ``snd``, not separate
primitives.
"""

from __future__ import annotations

from arc_lab.program_search.substrate.library import Primitive, Value
from arc_lab.program_search.substrate.types import TypeVar, pair_type

_A = TypeVar("a")
_B = TypeVar("b")
_PAIR_AB = pair_type(_A, _B)


def _pair(first: Value, second: Value) -> Value:
    return (first, second)


def _fst(value: Value) -> Value:
    if not isinstance(value, tuple) or len(value) != 2:
        raise TypeError(f"fst expects a pair, got {type(value).__name__}")
    return value[0]


def _snd(value: Value) -> Value:
    if not isinstance(value, tuple) or len(value) != 2:
        raise TypeError(f"snd expects a pair, got {type(value).__name__}")
    return value[1]


PAIR = Primitive(name="pair", param_types=(_A, _B), return_type=_PAIR_AB, impl=_pair)
FST = Primitive(name="fst", param_types=(_PAIR_AB,), return_type=_A, impl=_fst)
SND = Primitive(name="snd", param_types=(_PAIR_AB,), return_type=_B, impl=_snd)

PAIR_PRIMITIVES = (PAIR, FST, SND)
