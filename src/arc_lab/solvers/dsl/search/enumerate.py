"""Typed bottom-up enumeration of composed programs.

This is the general program-synthesis engine the whole DSL direction is built
toward. It grows programs from the leaves up, one composition round at a time:

* **Types prune the space.** A primitive's arguments are drawn only from the pool
  of programs of the matching :class:`ValueType`, so ill-typed compositions are
  never formed. This is what keeps an atomic vocabulary tractable.
* **Observational equivalence collapses it further.** Two programs that produce
  identical results on every training input are interchangeable; we keep only the
  first (smallest) representative of each behaviour. The number of distinct
  *behaviours* is far smaller than the number of syntactic programs, and this
  dedup is the same signal a future library-learning step will mine for reusable
  abstractions.

Constant leaves (colors, integers) are drawn from the task itself, so the search
never enumerates values that could not possibly appear. Variadic primitives (the
combinators) are left to their own bespoke searches; enumeration composes the
fixed-arity, atomic vocabulary.
"""

from __future__ import annotations

import itertools
import logging
from typing import TypeAlias

import numpy as np

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search.base import Search
from arc_lab.solvers.dsl.substrate.library import Library, Value
from arc_lab.solvers.dsl.substrate.program import (
    Apply,
    Const,
    Input,
    Program,
    evaluate,
    format_program,
)
from arc_lab.solvers.dsl.substrate.types import ValueType

logger = logging.getLogger(__name__)

Signature: TypeAlias = tuple[Value, ...]


def _format_value(value: Value) -> str:
    """Compact rendering of a single behaviour value (grids never materialise)."""
    if isinstance(value, Grid):
        return f"grid{value.height}x{value.width}#{hash(value) & 0xFFFFFF:06x}"
    return str(value)


def _format_signature(sig: Signature) -> str:
    """Compact rendering of a program's behaviour signature across training inputs."""
    return "(" + ", ".join(_format_value(v) for v in sig) + ")"


class Enumerate(Search):
    """Bottom-up, type-directed enumeration up to a bounded composition depth."""

    def __init__(
        self,
        *,
        max_depth: int = 2,
        max_pool: int = 600,
        max_grid_args: int = 16,
    ) -> None:
        self.max_depth = max_depth
        self.max_pool = max_pool
        # Cap on how many grid programs feed a composition round. Distinct grid
        # *behaviours* are few; this bounds the map_color(grid, color, color)
        # blow-up (grids x colors^2) without losing the simple, early programs.
        self.max_grid_args = max_grid_args

    def find(self, task: Task, library: Library) -> list[Program]:
        debug = logger.isEnabledFor(logging.DEBUG)
        inputs = [ex.input for ex in task.train]
        outputs = [ex.output for ex in task.train]
        if any(out is None for out in outputs):
            return []
        target: Signature = tuple(out for out in outputs if out is not None)

        # pools[type][behaviour-signature] = smallest program with that behaviour.
        pools: dict[ValueType, dict[Signature, Program]] = {
            ValueType.GRID: {},
            ValueType.COLOR: {},
            ValueType.INT: {},
        }

        def consider(program: Program, expected: ValueType) -> None:
            try:
                sig = tuple(evaluate(program, inp, library) for inp in inputs)
            except Exception as exc:
                if debug:
                    logger.debug(
                        "enumerate reject (eval error) %s: %s", format_program(program), exc
                    )
                return
            if expected == ValueType.GRID and not all(isinstance(v, Grid) for v in sig):
                if debug:
                    logger.debug("enumerate reject (non-grid) %s", format_program(program))
                return
            bucket = pools[expected]
            existing = bucket.get(sig)
            if existing is None:
                if debug:
                    logger.debug(
                        "enumerate accept [%s] %s sig=%s",
                        expected.value,
                        format_program(program),
                        _format_signature(sig),
                    )
                bucket[sig] = program
            elif debug:
                logger.debug(
                    "enumerate reject (dup of %s) %s",
                    format_program(existing),
                    format_program(program),
                )

        # Leaves: the input grid, and task-relevant color/int constants.
        consider(Input(), ValueType.GRID)
        colors, ints = _leaf_constants(task)
        for color in colors:
            consider(Const(color, ValueType.COLOR), ValueType.COLOR)
        for value in ints:
            consider(Const(value, ValueType.INT), ValueType.INT)

        fixed = [prim for prim in library.primitives if not prim.is_variadic]

        for _ in range(self.max_depth):
            if target in pools[ValueType.GRID]:
                break
            # Freeze the current pools so this round composes only prior programs.
            # Grid options are capped (simplest first) to bound the combination count.
            frozen = {vtype: list(bucket.values()) for vtype, bucket in pools.items()}
            frozen[ValueType.GRID] = frozen[ValueType.GRID][: self.max_grid_args]
            for prim in fixed:
                options = [frozen[t] for t in prim.param_types]
                if any(not opt for opt in options):
                    continue
                for combo in itertools.product(*options):
                    consider(Apply(prim.name, tuple(combo)), prim.return_type)
            if sum(len(b) for b in pools.values()) > self.max_pool:
                break

        if debug:
            logger.debug(
                "enumerate pools: grid=%d color=%d int=%d",
                len(pools[ValueType.GRID]),
                len(pools[ValueType.COLOR]),
                len(pools[ValueType.INT]),
            )
        found = pools[ValueType.GRID].get(target)
        return [found] if found is not None else []


def _leaf_constants(task: Task) -> tuple[list[int], list[int]]:
    """Task-relevant constants: colors that appear, and a consistent scale factor."""
    grids: list[Grid] = []
    for ex in task.train:
        grids.append(ex.input)
        if ex.output is not None:
            grids.append(ex.output)
    colors = sorted({int(c) for g in grids for c in np.unique(g.array)})

    ratios: list[int | None] = []
    for ex in task.train:
        if ex.output is None:
            ratios.append(None)
            continue
        ih, iw = ex.input.shape
        oh, ow = ex.output.shape
        if ih and iw and oh % ih == 0 and ow % iw == 0 and oh // ih == ow // iw > 1:
            ratios.append(oh // ih)
        else:
            ratios.append(None)
    ints: list[int] = []
    if ratios and all(r is not None and r == ratios[0] for r in ratios):
        assert ratios[0] is not None
        ints.append(ratios[0])
    return colors, ints
