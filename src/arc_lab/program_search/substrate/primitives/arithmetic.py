"""L0 integer extras (ONTOLOGY.md): the arithmetic beyond ``build.py``'s affine family.

``add``/``sub``/``mul`` stay in ``build.py`` (they are the D4-rederivation / affine-coordinate
clique documented there); these are the general-purpose remainder. ``floordiv``/``mod`` raise on a
zero divisor — pruned as ``⊥`` like any runtime error.
"""

from __future__ import annotations

from arc_lab.program_search.substrate.library import Primitive
from arc_lab.program_search.substrate.types import INT


def _min(a: int, b: int) -> int:
    return min(a, b)


def _max(a: int, b: int) -> int:
    return max(a, b)


def _abs(a: int) -> int:
    return abs(a)


def _floordiv(a: int, b: int) -> int:
    return a // b  # b == 0 raises ZeroDivisionError -> pruned as ⊥


def _mod(a: int, b: int) -> int:
    return a % b  # b == 0 raises ZeroDivisionError -> pruned as ⊥


MIN = Primitive(name="min", param_types=(INT, INT), return_type=INT, impl=_min)
MAX = Primitive(name="max", param_types=(INT, INT), return_type=INT, impl=_max)
ABS = Primitive(name="abs", param_types=(INT,), return_type=INT, impl=_abs)
FLOORDIV = Primitive(name="floordiv", param_types=(INT, INT), return_type=INT, impl=_floordiv)
MOD = Primitive(name="mod", param_types=(INT, INT), return_type=INT, impl=_mod)

ARITHMETIC_PRIMITIVES = (MIN, MAX, ABS, FLOORDIV, MOD)
