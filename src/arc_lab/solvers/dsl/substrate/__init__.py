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
from arc_lab.solvers.dsl.substrate.program import (
    Apply,
    Const,
    Input,
    Program,
    evaluate,
    evaluate_grid,
    format_program,
    is_consistent,
    program_from_dict,
    program_to_dict,
)
from arc_lab.solvers.dsl.substrate.types import ValueType

__all__ = [
    "Apply",
    "Const",
    "Input",
    "Library",
    "Primitive",
    "Program",
    "Value",
    "ValueType",
    "evaluate",
    "evaluate_grid",
    "format_program",
    "is_consistent",
    "program_from_dict",
    "program_to_dict",
]
