"""Solvers: pluggable strategies for predicting ARC task outputs.

Every solver implements the same narrow :class:`~arc_lab.solvers.base.Solver`
interface, so the scorer, runner, and CLI treat them interchangeably. Register a
new solver in :data:`REGISTRY` to make it available from the command line.
"""

from __future__ import annotations

from collections.abc import Callable

from arc_lab.solvers.base import Solver
from arc_lab.solvers.baseline import IdentitySolver
from arc_lab.solvers.dsl import GeometricSearchSolver

# name -> zero-argument factory. Kept as factories so constructing the registry
# never imports optional dependencies (e.g. the LLM solver needs `anthropic`).
REGISTRY: dict[str, Callable[[], Solver]] = {
    "identity": IdentitySolver,
    "dsl": GeometricSearchSolver,
}


def _make_llm() -> Solver:
    from arc_lab.solvers.llm import ClaudeSolver

    return ClaudeSolver()


REGISTRY["llm"] = _make_llm


def make_solver(name: str) -> Solver:
    """Instantiate a registered solver by name."""
    try:
        factory = REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(REGISTRY))
        raise KeyError(f"unknown solver {name!r}; known solvers: {known}") from None
    return factory()


__all__ = ["REGISTRY", "Solver", "make_solver"]
