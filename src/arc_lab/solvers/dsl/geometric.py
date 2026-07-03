"""A small program-search solver over whole-grid geometric transforms.

This is the seed of the "DSL + program search" direction, and a faithful (if
tiny) illustration of the pattern:

1. define a vocabulary of primitive operations (here: identity, rotations,
   flips, transpose, and their compositions);
2. keep every primitive that reproduces the output from the input on **all**
   training examples;
3. apply the surviving primitives to each test input, best-consistency first.

It solves the subset of ARC tasks whose rule is a single rigid transform — a
real, non-trivial slice of ARC-1 — and its structure generalises directly to a
richer DSL (object extraction, recoloring, tiling, ...).
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import numpy.typing as npt

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.solvers.base import Prediction, Solver

Transform = Callable[[npt.NDArray[np.int8]], npt.NDArray[np.int8]]

# The primitive vocabulary. Order matters only as a tie-break: earlier, simpler
# transforms are preferred when several are equally consistent with training.
_PRIMITIVES: dict[str, Transform] = {
    "identity": lambda a: a,
    "rot90": lambda a: np.rot90(a, 1),
    "rot180": lambda a: np.rot90(a, 2),
    "rot270": lambda a: np.rot90(a, 3),
    "flip_h": np.fliplr,
    "flip_v": np.flipud,
    "transpose": lambda a: a.T,
    "anti_transpose": lambda a: np.rot90(a, 2).T,
}


class GeometricSearchSolver(Solver):
    """Search whole-grid geometric transforms for one consistent with training."""

    name = "dsl"

    def predict(self, task: Task) -> Prediction:
        consistent = self._consistent_transforms(task)
        # Fall back to identity so we always return a well-formed prediction.
        chosen = consistent or ["identity"]
        return [[self._apply(name, example.input) for name in chosen] for example in task.test]

    def _consistent_transforms(self, task: Task) -> list[str]:
        """Names of primitives that map every train input to its output."""
        survivors: list[str] = []
        for name, fn in _PRIMITIVES.items():
            if all(
                ex.output is not None and np.array_equal(fn(ex.input.array), ex.output.array)
                for ex in task.train
            ):
                survivors.append(name)
        return survivors

    @staticmethod
    def _apply(name: str, grid: Grid) -> Grid:
        return Grid(_PRIMITIVES[name](grid.array))
