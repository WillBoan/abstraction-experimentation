"""DSL / program-search solvers.

Solvers here build a program from a typed vocabulary (a *library* of primitives)
and search for one consistent with the training examples.

The reusable machinery lives in:

- :mod:`~arc_lab.solvers.dsl.substrate` (types, programs-as-data, libraries,
combinators)
- :mod:`~arc_lab.solvers.dsl.search` (search strategies)

A concrete solver is a :class:`ProgramSearchSolver` built from a declarative
:class:`~arc_lab.solvers.dsl.config.Config` (a *(library, search, cost)* triple).
Named presets — the historical ``dsl`` / ``dsl-sym`` / ``dsl-synth`` / ``dsl-beam``
wirings, now data — live in :mod:`~arc_lab.solvers.dsl.config`.
"""

from arc_lab.solvers.dsl.solver import ProgramSearchSolver

__all__ = [
    "ProgramSearchSolver",
]
