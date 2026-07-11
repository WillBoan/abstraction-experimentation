"""Solvers: pluggable strategies for predicting ARC task outputs.

Every solver implements the same narrow :class:`~arc_lab.solvers.base.Solver`
interface, so the scorer, runner, and CLI treat them interchangeably. Register a
new solver in :data:`REGISTRY` to make it available from the command line.
"""

from __future__ import annotations

from collections.abc import Callable

from arc_lab.solvers.base import Solver
from arc_lab.solvers.baseline import IdentitySolver
from arc_lab.solvers.dsl.config import PRESETS
from arc_lab.solvers.dsl.solver import ProgramSearchSolver


def _preset_factory(name: str) -> Callable[[], Solver]:
    """A zero-arg factory that builds the named machinery preset on demand."""
    return lambda: ProgramSearchSolver.from_config(PRESETS[name])


# name -> zero-argument factory. The DSL solvers build from named ``Config`` presets
# (config-as-data); factories keep optional deps (e.g. the LLM's `anthropic`) unimported.
REGISTRY: dict[str, Callable[[], Solver]] = {
    "identity": IdentitySolver,
    **{name: _preset_factory(name) for name in PRESETS},
}


def make_solver(name: str) -> Solver:
    """Instantiate a registered solver by name."""
    try:
        factory = REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(REGISTRY))
        raise KeyError(f"unknown solver {name!r}; known solvers: {known}") from None
    return factory()


__all__ = ["REGISTRY", "Solver", "make_solver"]
