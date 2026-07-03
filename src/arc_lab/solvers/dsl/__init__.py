"""DSL / program-search solvers.

This package holds solvers that build a candidate program from a small vocabulary
of grid operations and search for one consistent with the training examples. It
starts intentionally tiny (whole-grid geometric transforms) so the *search over
a DSL* pattern is legible; the vocabulary is meant to grow.
"""

from arc_lab.solvers.dsl.geometric import GeometricSearchSolver

__all__ = ["GeometricSearchSolver"]
