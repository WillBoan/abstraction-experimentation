"""Search for a mosaic program built on the ``tile`` combinator.

The layout is *inferred* from the first training pair — read off how many blocks
the output divides into and which D4 transform each block is — then the resulting
``tile(rows, cols, cell₀(Input), …)`` program is verified against every pair.
Inference beats blind enumeration here: the output tells us the layout directly.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from arc_lab.core.grid import Grid
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


class TileSearch(Search):
    """Find a consistent ``tile(rows, cols, cells…)`` program, or none."""

    #: Largest tiling factor to consider per axis.
    max_factor: int = 3

    def find(self, task: Task, library: Library) -> list[Program]:
        pairs = [(ex.input, ex.output) for ex in task.train]
        if any(out is None for _, out in pairs):
            return []
        transforms = [prim.name for prim in library.unary_grid_primitives()]
        first_in, first_out = pairs[0]
        layout = self._infer_layout(first_in, first_out, transforms, library)  # type: ignore[arg-type]
        if layout is None:
            return []
        rows, cols, cells = layout
        program: Program = Apply(
            "tile",
            (
                Const(rows, ValueType.INT),
                Const(cols, ValueType.INT),
                *(Apply(name, (Input(),)) for name in cells),
            ),
        )
        return [program] if is_consistent(program, task, library) else []

    def _infer_layout(
        self, inp: Grid, out: Grid, transforms: list[str], library: Library
    ) -> tuple[int, int, tuple[str, ...]] | None:
        ih, iw = inp.shape
        oh, ow = out.shape
        if oh % ih or ow % iw:
            return None
        rows, cols = oh // ih, ow // iw
        if not (1 <= rows <= self.max_factor and 1 <= cols <= self.max_factor):
            return None
        if (rows, cols) == (1, 1):
            return None
        out_arr = out.array
        cells: list[str] = []
        for r in range(rows):
            for c in range(cols):
                block = out_arr[r * ih : (r + 1) * ih, c * iw : (c + 1) * iw]
                match = self._match_block(inp, block, transforms, library)
                if match is None:
                    return None
                cells.append(match)
        return rows, cols, tuple(cells)

    @staticmethod
    def _match_block(
        inp: Grid, block: npt.NDArray[np.int8], transforms: list[str], library: Library
    ) -> str | None:
        for name in transforms:
            transformed = evaluate_grid(Apply(name, (Input(),)), inp, library).array
            if transformed.shape == block.shape and np.array_equal(transformed, block):
                return name
        return None
