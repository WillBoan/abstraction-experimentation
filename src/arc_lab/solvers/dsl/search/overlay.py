"""Search for a symmetry-repair program built on the ``overlay`` combinator.

Enumerates a mask color and a set of shape-preserving D4 symmetries, forming the
program ``overlay(mask, identity(Input), s1(Input), …)``, and keeps the most
constrained configuration consistent with every training pair.

ELI5 explanation: the output is a copy of the input, but with some pixels replaced by
the result of applying a symmetry to the input. The mask color tells us which pixels
to replace, and the symmetries tell us how to transform the input to get the replacement
pixels. The search finds the best combination of mask and symmetries that works for all
training examples.

EXAMPLE: if the input is a square and the output is a square with the top-left corner
replaced by the bottom-right corner, the search will find the mask color of the corner
and the symmetry that flips the square diagonally, and produce the program
``overlay(mask, identity(Input), flip_diagonal(Input))``.
"""

from __future__ import annotations

import itertools
import logging

import numpy as np

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search.base import Search, SearchResult, SearchStats
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Input, Program
from arc_lab.solvers.dsl.substrate.types import ValueType

logger = logging.getLogger(__name__)


class OverlaySearch(Search):
    """Find a consistent ``overlay(mask, symmetries…)`` program, or none."""

    #: Cap on how many non-identity symmetries to combine (keeps enumeration small).
    max_symmetries: int = 3

    def find(self, task: Task, library: Library) -> SearchResult:
        pairs = [(ex.input, ex.output) for ex in task.train]
        if any(out is None for _, out in pairs):
            stats = SearchStats(strategy="OverlaySearch", considered=0, returned=0)
            logger.info(stats.summary())
            return SearchResult(programs=(), stats=stats)
        # Overlay is same-shape by construction.
        if any(inp.shape != out.shape for inp, out in pairs):  # type: ignore[union-attr]
            stats = SearchStats(strategy="OverlaySearch", considered=0, returned=0)
            logger.info(stats.summary())
            return SearchResult(programs=(), stats=stats)
        inputs = [inp for inp, _ in pairs]

        # Symmetries usable here: non-identity D4 transforms that preserve the shape
        # of every training input (otherwise their copies can't be overlaid).
        candidates = [
            prim.name
            for prim in library.unary_grid_primitives()
            if prim.name != "identity"
            and all(
                Apply(prim.name, (Input(),)).evaluate_grid(inp, library).shape == inp.shape
                for inp in inputs
            )
        ]
        colors = sorted({int(c) for inp in inputs for c in np.unique(inp.array)})

        best: Program | None = None
        best_size = 0
        considered = 0
        skipped = 0
        accepted = 0
        for mask in colors:
            for size in range(1, self.max_symmetries + 1):
                for subset in itertools.combinations(candidates, size):
                    considered += 1
                    program: Program = Apply(
                        "overlay",
                        (
                            Const(mask, ValueType.COLOR),
                            Apply("identity", (Input(),)),
                            *(Apply(name, (Input(),)) for name in subset),
                        ),
                    )
                    if len(subset) <= best_size:
                        skipped += 1
                        logger.debug(
                            "Overlay skip (not more constrained than best=%d) mask=%d subset=%s",
                            best_size,
                            mask,
                            subset,
                        )
                        continue
                    if self.accepts(program, task, library):
                        accepted += 1
                        logger.debug("Overlay accept mask=%d subset=%s", mask, subset)
                        best, best_size = program, len(subset)
        programs: tuple[Program, ...] = (best,) if best is not None else ()
        stats = SearchStats(
            strategy="OverlaySearch",
            considered=considered,
            returned=len(programs),
            extra={"skipped": skipped, "accepted": accepted},
        )
        logger.info(stats.summary())
        return SearchResult(programs=programs, stats=stats)
