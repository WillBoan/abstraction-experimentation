"""The program-search substrate: the reusable machinery a program-search solver draws on.

This package holds *no solving logic*. It provides the pieces that different
solvers combine in different ways:

* :mod:`~arc_lab.solvers.program_search.substrate.types` — the value type system (what makes
  typed program search tractable);
* :mod:`~arc_lab.solvers.program_search.substrate.program` — programs as an inspectable AST
  (so they can be enumerated, evaluated, serialised, and later abstracted over);
* :mod:`~arc_lab.solvers.program_search.substrate.library` — a first-class, extensible set of
  typed primitives;
* :mod:`~arc_lab.solvers.program_search.substrate.primitives` — concrete primitive libraries.

A concrete solver is a choice of *(library, search strategy)* — see
:class:`~arc_lab.solvers.program_search.solver.ProgramSearchSolver`.
"""

from arc_lab.solvers.program_search.substrate.library import Library, Primitive, Value
from arc_lab.solvers.program_search.substrate.program import Apply, Const, Input, Param, Program
from arc_lab.solvers.program_search.substrate.types import (
    COLOR,
    FN,
    GRID,
    INT,
    ArrowType,
    Type,
    TypeCon,
    TypeVar,
    apply_subst,
    base_type,
    instantiate,
    list_type,
    pair_type,
    unify,
)

__all__ = [
    "COLOR",
    "FN",
    "GRID",
    "INT",
    "Apply",
    "ArrowType",
    "Const",
    "Input",
    "Library",
    "Param",
    "Primitive",
    "Program",
    "Type",
    "TypeCon",
    "TypeVar",
    "Value",
    "apply_subst",
    "base_type",
    "instantiate",
    "list_type",
    "pair_type",
    "unify",
]
