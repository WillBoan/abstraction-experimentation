"""DSL / program-search solvers.

Solvers here build a program from a typed vocabulary (a *library* of primitives)
and search for one consistent with the training examples.

The reusable machinery lives in:

- :mod:`~arc_lab.solvers.dsl.substrate` (types, programs-as-data, libraries,
combinators)
- :mod:`~arc_lab.solvers.dsl.search` (search strategies)

A concrete solver is just a *(library, search)* pairing.

It starts small — whole-grid geometric transforms searched by single application
(:class:`GeometricSearchSolver`) — and grows by *combinators over the same
vocabulary*: :class:`SymmetrySearchSolver` adds overlay-based symmetry repair and
mosaic tiling without introducing any new grid transform.
"""

from arc_lab.solvers.dsl.solver import (
    GeometricSearchSolver,
    ProgramSearchSolver,
    SymmetrySearchSolver,
    SynthesisSolver,
)

__all__ = [
    "GeometricSearchSolver",
    "ProgramSearchSolver",
    "SymmetrySearchSolver",
    "SynthesisSolver",
]
