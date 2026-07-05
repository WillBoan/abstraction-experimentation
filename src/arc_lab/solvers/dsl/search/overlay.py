"""Search for a symmetry-repair program built on the ``overlay`` combinator.

Enumerates a mask color and a set of shape-preserving D4 symmetries, forming the
program ``overlay(mask, identity(Input), s1(Input), …)``, and keeps the most
constrained configuration consistent with every training pair.
"""

from __future__ import annotations

import itertools

import numpy as np

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search.base import Search
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.program import (
    Apply,
    Const,
    Input,
    Program,
    evaluate_grid,
    is_consistent,
)
from arc_lab.solvers.dsl.substrate.types import ValueType


class OverlaySearch(Search):
    """Find a consistent ``overlay(mask, symmetries…)`` program, or none."""

    #: Cap on how many non-identity symmetries to combine (keeps enumeration small).
    max_symmetries: int = 3

    def find(self, task: Task, library: Library) -> list[Program]:
        pairs = [(ex.input, ex.output) for ex in task.train]
        if any(out is None for _, out in pairs):
            return []
        # Overlay is same-shape by construction.
        if any(inp.shape != out.shape for inp, out in pairs):  # type: ignore[union-attr]
            return []
        inputs = [inp for inp, _ in pairs]

        # Symmetries usable here: non-identity D4 transforms that preserve the shape
        # of every training input (otherwise their copies can't be overlaid).
        candidates = [
            prim.name
            for prim in library.unary_grid_primitives()
            if prim.name != "identity"
            and all(
                evaluate_grid(Apply(prim.name, (Input(),)), inp, library).shape == inp.shape
                for inp in inputs
            )
        ]
        colors = sorted({int(c) for inp in inputs for c in np.unique(inp.array)})

        best: Program | None = None
        best_size = 0
        for mask in colors:
            for size in range(1, self.max_symmetries + 1):
                for subset in itertools.combinations(candidates, size):
                    program: Program = Apply(
                        "overlay",
                        (
                            Const(mask, ValueType.COLOR),
                            Apply("identity", (Input(),)),
                            *(Apply(name, (Input(),)) for name in subset),
                        ),
                    )
                    if len(subset) > best_size and is_consistent(program, task, library):
                        best, best_size = program, len(subset)
        return [best] if best is not None else []
