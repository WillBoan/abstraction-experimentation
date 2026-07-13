"""The program-search substrate: the language that search and learning operate over.

This package holds *no search logic*. It provides the pieces the other layers
combine:

* :mod:`~arc_lab.program_search.substrate.types` — the value type system (what makes
  typed program search tractable);
* :mod:`~arc_lab.program_search.substrate.program` — programs as an inspectable AST
  (so they can be enumerated, evaluated, serialised, and later abstracted over);
* :mod:`~arc_lab.program_search.substrate.library` — a first-class, extensible set of
  typed primitives;
* :mod:`~arc_lab.program_search.substrate.primitives` — concrete primitive libraries.

A configured search is a :class:`~arc_lab.program_search.execution.model.config.Config`
(library x search engine x budget); the execution layer drives it directly.
"""

from arc_lab.program_search.substrate.library import Library, Primitive, Value
from arc_lab.program_search.substrate.program import Apply, Const, Input, Param, Program
from arc_lab.program_search.substrate.types import (
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
