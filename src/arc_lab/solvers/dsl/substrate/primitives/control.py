"""Domain-agnostic control primitives: comparisons, boolean logic, and branching.

These are the small L0 block that turns ``build_grid + read`` from a geometric renderer into a
general per-cell decision language. The signatures are intentionally typed at the DSL level rather
than by Python overloads: ``eq`` and ``if`` are first-order polymorphic over the existing base types,
while ordering stays integer-only.
"""

from __future__ import annotations

from arc_lab.solvers.dsl.substrate.library import Primitive, Value
from arc_lab.solvers.dsl.substrate.types import BOOL, INT, TypeVar

_A = TypeVar("a")


def _eq(left: Value, right: Value) -> bool:
    return bool(left == right)


def _lt(left: int, right: int) -> bool:
    return left < right


def _gt(left: int, right: int) -> bool:
    return left > right


def _and(left: bool, right: bool) -> bool:
    return left and right


def _or(left: bool, right: bool) -> bool:
    return left or right


def _not(value: bool) -> bool:
    return not value


def _if(cond: bool, when_true: Value, when_false: Value) -> Value:
    return when_true if cond else when_false


EQ = Primitive(name="eq", param_types=(_A, _A), return_type=BOOL, impl=_eq)
LT = Primitive(name="lt", param_types=(INT, INT), return_type=BOOL, impl=_lt)
GT = Primitive(name="gt", param_types=(INT, INT), return_type=BOOL, impl=_gt)
AND = Primitive(name="and", param_types=(BOOL, BOOL), return_type=BOOL, impl=_and)
OR = Primitive(name="or", param_types=(BOOL, BOOL), return_type=BOOL, impl=_or)
NOT = Primitive(name="not", param_types=(BOOL,), return_type=BOOL, impl=_not)
IF = Primitive(name="if", param_types=(BOOL, _A, _A), return_type=_A, impl=_if)

CONTROL_PRIMITIVES = (EQ, LT, GT, AND, OR, NOT, IF)
