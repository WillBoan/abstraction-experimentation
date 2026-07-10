"""The DSL substrate: the reusable machinery a program-search solver draws on.

This package holds *no solving logic*. It provides the pieces that different
solvers combine in different ways:

* :mod:`~arc_lab.solvers.dsl.substrate.types` — the value type system (what makes
  typed program search tractable);
* :mod:`~arc_lab.solvers.dsl.substrate.program` — programs as an inspectable AST
  (so they can be enumerated, evaluated, serialised, and later abstracted over);
* :mod:`~arc_lab.solvers.dsl.substrate.library` — a first-class, extensible set of
  typed primitives;
* :mod:`~arc_lab.solvers.dsl.substrate.primitives` — concrete primitive libraries.

A concrete solver is a choice of *(library, search strategy)* — see
:class:`~arc_lab.solvers.dsl.solver.ProgramSearchSolver`.
"""

from arc_lab.solvers.dsl.substrate.library import Library, Primitive, Value
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Input, Param, Program
from arc_lab.solvers.dsl.substrate.types import (
    COLOR,
    FN,
    GRID,
    INT,
    ArrowType,
    BaseType,
    Type,
    TypeVar,
    apply_subst,
    base_type,
    instantiate,
    unify,
)

__all__ = [
    "COLOR",
    "FN",
    "GRID",
    "INT",
    "Apply",
    "ArrowType",
    "BaseType",
    "Const",
    "Input",
    "Library",
    "Param",
    "Primitive",
    "Program",
    "Type",
    "TypeVar",
    "Value",
    "apply_subst",
    "base_type",
    "instantiate",
    "unify",
]
