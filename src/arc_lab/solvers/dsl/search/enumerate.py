"""Typed bottom-up enumeration of composed programs.

This is the general program-synthesis engine the whole DSL direction is built
toward. It grows programs from the leaves up, one composition round at a time:

* **Types prune the space.** A primitive's arguments are drawn only from the pool
  of programs of the matching :class:`ValueType`, so ill-typed compositions are
  never formed. This is what keeps an atomic vocabulary tractable.
* **Observational equivalence collapses it further.** Two programs that produce
  identical results on every training input are interchangeable; we keep only the
  *smallest* representative of each behaviour (a later, smaller-node-count equivalent
  replaces an earlier one). The number of distinct *behaviours* is far smaller than
  the number of syntactic programs, and this dedup is the same signal a future
  library-learning step will mine for reusable abstractions.

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
from arc_lab.solvers.dsl.search.base import Search, SearchResult, SearchStats
from arc_lab.solvers.dsl.search.cost import Cost
from arc_lab.solvers.dsl.substrate.library import Library, Value
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Input, Program
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
        coord_ints: bool = False,
    ) -> None:
        # Enumerate enforces consistency implicitly (a program is kept only if its
        # behaviour signature equals the training outputs), so it does not take or
        # apply Constraint objects; the default keeps the base contract satisfied.
        super().__init__()
        self.max_depth = max_depth
        self.max_pool = max_pool
        # Cap on how many grid programs feed a composition round. Distinct grid
        # *behaviours* are few; this bounds the map_color(grid, color, color)
        # blow-up (grids x colors^2) without losing the simple, early programs.
        self.max_grid_args = max_grid_args
        # Mine coordinate INT leaves (0..max grid dimension) for cell-level primitives
        # (read/set_cell). Off by default so the existing INT-consuming vocabularies
        # (scale) are unaffected — keeping the dsl-synth lock intact.
        self.coord_ints = coord_ints

    def find(self, task: Task, library: Library) -> SearchResult:
        debug = logger.isEnabledFor(logging.DEBUG)
        inputs = [ex.input for ex in task.train]
        outputs = [ex.output for ex in task.train]
        if any(out is None for out in outputs):
            stats = SearchStats(strategy="Enumerate", considered=0, returned=0)
            logger.info(stats.summary())
            return SearchResult(programs=(), stats=stats)
        target: Signature = tuple(out for out in outputs if out is not None)

        # pools[type][behaviour-signature] = smallest program with that behaviour.
        pools: dict[ValueType, dict[Signature, Program]] = {
            ValueType.GRID: {},
            ValueType.COLOR: {},
            ValueType.INT: {},
        }

        # Per-search tallies for the INFO summary (cheap; maintained unconditionally).
        counts = {"considered": 0, "kept": 0, "dup": 0, "err": 0, "nongrid": 0}

        # TODO(trace-volume, optional): the four `logger.debug` sites below are the
        # firehose (~600 lines/task today, and it grows with max_depth and library
        # size). If it becomes unwieldy, split them onto child loggers
        # (`{__name__}.accept` / `.reject`) so you can keep accepts and mute the
        # dedup stream independently, e.g. set `...enumerate.reject` to WARNING while
        # the parent stays at DEBUG. Not worth the indirection until the volume
        # actually gets in the way — the `if debug:` guard already makes it free when off.
        def consider(program: Program, expected: ValueType) -> None:
            counts["considered"] += 1
            try:
                sig: Signature = tuple(program.evaluate(inp, library) for inp in inputs)
            except Exception as exc:
                counts["err"] += 1
                if debug:
                    logger.debug("enumerate reject (eval error) %s: %s", program, exc)
                return
            if expected == ValueType.GRID and not all(isinstance(v, Grid) for v in sig):
                counts["nongrid"] += 1
                if debug:
                    logger.debug("enumerate reject (non-grid) %s", program)
                return
            bucket = pools[expected]
            existing = bucket.get(sig)
            if existing is None:
                counts["kept"] += 1
                if debug:
                    logger.debug(
                        "enumerate accept [%s] %s sig=%s",
                        expected.value,
                        program,
                        _format_signature(sig),
                    )
                bucket[sig] = program
            elif program.size() < existing.size():
                # Same behaviour, fewer nodes: keep the *smallest* witness per behaviour, not
                # merely the first considered. Discovery order tracks size loosely (later rounds
                # are deeper) but not exactly — within a round a multi-arity primitive can form a
                # larger equivalent before a smaller one, and library order decides which lands
                # first. Keeping the smaller one hands the sleep step minimal programs, removing
                # the latent bloat root cause. The *set* of reachable behaviours is unchanged —
                # only the representative shrinks — so which tasks solve is invariant.
                counts["dup"] += 1
                if debug:
                    logger.debug("enumerate replace (smaller than %s) %s", existing, program)
                bucket[sig] = program
            else:
                counts["dup"] += 1
                if debug:
                    logger.debug("enumerate reject (dup of %s) %s", existing, program)

        # Leaves: the input grid, and task-relevant color/int constants.
        consider(Input(), ValueType.GRID)
        colors, ints = _leaf_constants(task, coord_ints=self.coord_ints)
        for color in colors:
            consider(Const(color, ValueType.COLOR), ValueType.COLOR)
        for value in ints:
            consider(Const(value, ValueType.INT), ValueType.INT)

        fixed = [prim for prim in library.primitives if not prim.is_variadic]

        # TODO(checkpointing, deferred): the run artifact checkpoints at *task* grain
        # (streaming trace + resume, see analysis/runner.py), which is the right grain
        # while a single task's search is fast. If a lower primitive floor ever makes one
        # task's enumeration take minutes, add *intra-task* checkpointing here — serialise
        # the frozen pools between rounds so an interrupted search resumes mid-task. Not
        # worth the coupling to engine internals until that cost is actually observed.
        for _ in range(self.max_depth):
            if target in pools[ValueType.GRID]:
                break
            # Freeze the current pools so this round composes only prior programs.
            # The grid frontier is capped (the overridable F1 frontier policy) to bound the count.
            frozen = {vtype: list(bucket.values()) for vtype, bucket in pools.items()}
            frozen[ValueType.GRID] = self._grid_frontier(frozen[ValueType.GRID], task, library)
            for prim in fixed:
                options = [frozen[t] for t in prim.param_types]
                if any(not opt for opt in options):
                    continue
                for combo in itertools.product(*options):
                    consider(Apply(prim.name, tuple(combo)), prim.return_type)
            if sum(len(b) for b in pools.values()) > self.max_pool:
                break

        found = pools[ValueType.GRID].get(target)
        programs: tuple[Program, ...] = (found,) if found is not None else ()
        stats = SearchStats(
            strategy="Enumerate",
            considered=counts["considered"],
            returned=len(programs),
            extra={
                "kept": counts["kept"],
                "deduped": counts["dup"],
                "errored": counts["err"],
                "nongrid": counts["nongrid"],
                "pool_grid": len(pools[ValueType.GRID]),
                "pool_color": len(pools[ValueType.COLOR]),
                "pool_int": len(pools[ValueType.INT]),
            },
        )
        logger.info(stats.summary())
        return SearchResult(programs=programs, stats=stats)

    def _grid_frontier(
        self, candidates: list[Program], task: Task, library: Library
    ) -> list[Program]:
        """The grid programs that feed the next composition round — the frontier policy.

        The default is a blind insertion-order cut (``max_grid_args``): it keeps the
        earliest-found — and, post keep-smallest, smallest — grids. ``task``/``library`` are
        unused here but are the inputs a *cost*-ranked policy needs, so a subclass
        (:class:`BeamSearch`) can override this one seam without touching the search loop.
        """
        return candidates[: self.max_grid_args]


class BeamSearch(Enumerate):
    """Cost-guided enumeration: keep the top-``beam_width`` grid programs per round by ``Cost``.

    Identical to :class:`Enumerate` except the per-round grid frontier is *ranked by an injected*
    :class:`~arc_lab.solvers.dsl.search.cost.Cost` and truncated to ``beam_width``, rather than
    cut in insertion order. This is the first search to actually *consume* a ``Cost`` — the rank
    the substrate defines but the frontier never used — turning ``max_grid_args`` from
    'simplest-by-arrival' into 'cheapest-by-cost'. That is what a richer (object / cell-floor)
    vocabulary needs to stay tractable once the grid pool would otherwise explode. The accumulated
    behaviour pools are unchanged; only *which* grids feed the next round is cost-selected.
    """

    def __init__(
        self,
        *,
        cost: Cost,
        beam_width: int = 16,
        max_depth: int = 2,
        max_pool: int = 600,
        coord_ints: bool = False,
    ) -> None:
        super().__init__(
            max_depth=max_depth,
            max_pool=max_pool,
            max_grid_args=beam_width,
            coord_ints=coord_ints,
        )
        self.cost = cost
        self.beam_width = beam_width

    def _grid_frontier(
        self, candidates: list[Program], task: Task, library: Library
    ) -> list[Program]:
        # Rank the whole grid pool by cost (lower first) and keep the cheapest beam_width. A
        # stable sort preserves insertion (smallest-first) order among cost ties.
        ranked = sorted(candidates, key=lambda program: self.cost.of(program, task, library))
        return ranked[: self.beam_width]


def _leaf_constants(task: Task, *, coord_ints: bool = False) -> tuple[list[int], list[int]]:
    """Task-relevant constants: colors, a consistent scale factor, and (opt) coordinates."""
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
    ints: set[int] = set()
    if ratios and all(r is not None and r == ratios[0] for r in ratios):
        assert ratios[0] is not None
        ints.add(ratios[0])
    if coord_ints:
        # Every in-bounds row/col index of the input grids, for read/set_cell.
        max_dim = max((max(ex.input.shape) for ex in task.train), default=0)
        ints.update(range(max_dim))
    return colors, sorted(ints)
