"""Bespoke search for size-general ``build_grid`` programs — open coordinate lambdas.

`Enumerate` cannot find these: a ``build_grid`` body is an **open term** (it has free ``$i``
bound variables, meaningful only inside the loop), so it can't live in the closed-term pools of
the general engine. This search handles the open term directly, the way `OverlaySearch`/`TileSearch`
handle their bespoke combinators:

1. **Enumerate INT coordinate-expressions** over the body-context leaves — the two bound coords
   (``$0`` = col ``j``, ``$1`` = row ``i``), the ``width``/``height`` perceivers, and small consts —
   composed with every ``INT^n -> INT`` primitive the library carries (``sub``/``add``/``mul``, and
   any *learned* coordinate abstraction such as ``mirror_index``), bottom-up to a bounded depth. Two
   programs are equivalent iff they agree at every ``(train input, output cell)`` sample
   (observational equivalence lifted to cells); a cost-beam bounds the pool each round.
2. **Assemble + verify.** For each dimension pair (from ``width``/``height``) and each ordered pair
   of coordinate expressions, form ``build_grid(dh, dw, lam(lam(read(input, row, col))))`` and keep
   the smallest program consistent with every training pair.

Wrong coordinate math self-eliminates — an out-of-bounds ``read`` raises and the candidate is
discarded — and observational-equivalence dedup collapses distinct syntax computing the same
coordinate function, so this is generate-and-test over *behaviours*, not raw syntax. Its cost is the
``(pool size)^2`` assembly over deep coordinate expressions: that is where it strains (the deep D4
members), which is the point of the probe. Assumes ``library`` provides ``build_grid``/``read``/
``width``/``height``/``sub`` (e.g. ``BUILD_LIBRARY``).
"""

from __future__ import annotations

import itertools
import logging
from typing import TypeAlias

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search.base import Search, SearchResult, SearchStats
from arc_lab.solvers.dsl.search.cost import Cost, ProgramSize
from arc_lab.solvers.dsl.substrate.library import Library, Value
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Input, Lam, Program, Var
from arc_lab.solvers.dsl.substrate.types import ValueType

logger = logging.getLogger(__name__)

_INT = ValueType.INT
CellSig: TypeAlias = tuple[Value, ...]


class BuildGridSearch(Search):
    """Find a size-general ``build_grid`` program (open coordinate-lambda body), or none."""

    def __init__(
        self,
        *,
        cost: Cost | None = None,
        max_coord_depth: int = 2,
        beam_width: int = 128,
        consts: tuple[int, ...] = (0, 1),
    ) -> None:
        # Verification is the default ConsistentWithTraining (via self.accepts).
        super().__init__()
        self.cost = cost or ProgramSize()
        self.max_coord_depth = max_coord_depth
        self.beam_width = beam_width
        self.consts = consts

    def composes_signature(
        self, param_types: tuple[ValueType, ...], return_type: ValueType
    ) -> bool:
        """Whether the coordinate enumeration composes a primitive of this signature (``INT^n -> INT``).

        The search's own composition rule, exposed so a ``SearchScopedFrequentSubtree`` can mine
        exactly the coordinate idioms this search can *reuse* (e.g. a learned ``mirror_index``).
        """
        return return_type == _INT and bool(param_types) and all(pt == _INT for pt in param_types)

    def find(self, task: Task, library: Library) -> SearchResult:
        pairs: list[tuple[Grid, Grid]] = []
        for ex in task.train:
            if ex.output is None:
                return self._result(strategy_extra={}, programs=(), considered=0)
            pairs.append((ex.input, ex.output))
        # The cells a body must reproduce: every coordinate of every training output.
        battery = [
            (inp, i, j) for inp, out in pairs for i in range(out.height) for j in range(out.width)
        ]
        if not battery:
            return self._result(strategy_extra={}, programs=(), considered=0)

        int_pool = self._coordinate_pool(battery, task, library)
        return self._assemble(int_pool, pairs, task, library)

    # -- INT coordinate-expression enumeration (cell-battery obs-equivalence) --

    def _coordinate_pool(
        self, battery: list[tuple[Grid, int, int]], task: Task, library: Library
    ) -> list[Program]:
        """Distinct coordinate functions over ``{$0, $1, width, height, consts}`` composed with sub."""
        pool: dict[CellSig, Program] = {}

        def signature(expr: Program) -> CellSig | None:
            try:
                return tuple(expr.evaluate(inp, library, (), (i, j)) for inp, i, j in battery)
            except Exception:  # an ill-formed expr just doesn't enter the pool
                return None

        def consider(expr: Program) -> None:
            sig = signature(expr)
            if sig is None:
                return
            existing = pool.get(sig)
            if existing is None or expr.size() < existing.size():
                pool[sig] = expr  # keep the smallest witness per coordinate behaviour

        leaves: list[Program] = [
            Var(0, _INT),  # $0 = column j (innermost binder)
            Var(1, _INT),  # $1 = row i (outer binder)
            Apply("width", (Input(),)),
            Apply("height", (Input(),)),
            *(Const(c, _INT) for c in self.consts),
        ]
        for leaf in leaves:
            consider(leaf)
        # Composition is *primitive-driven*: every INT^n -> INT primitive the library carries (sub,
        # add, mul, and any *learned* coordinate abstraction like mirror_index). This is what makes
        # a minted abstraction actually usable by the search -- and behaviour-identical to the old
        # hardcoded `sub` whenever `sub` is the only such primitive (e.g. BUILD_LIBRARY).
        int_ops = [
            prim
            for prim in library.primitives
            if not prim.is_variadic and self.composes_signature(prim.param_types, prim.return_type)
        ]
        for _ in range(self.max_coord_depth):
            frozen = sorted(pool.values(), key=lambda e: self.cost.of(e, task, library))
            frozen = frozen[: self.beam_width]  # cost-beam: compose only the cheapest so far
            for prim in int_ops:
                for combo in itertools.product(frozen, repeat=len(prim.param_types)):
                    consider(Apply(prim.name, combo))
        return sorted(pool.values(), key=lambda e: self.cost.of(e, task, library))[
            : self.beam_width
        ]

    def _matching_dims(
        self, pairs: list[tuple[Grid, Grid]], library: Library
    ) -> list[tuple[Program, Program]]:
        """The ``(height, width)`` expression pairs (from width/height) that yield the output shape.

        A D4 member's output is a permutation of the input dims, so only one of the four pairings
        fits — pruning to it quarters the assembly (and is a correctness filter besides).
        """
        exprs: list[Program] = [Apply("width", (Input(),)), Apply("height", (Input(),))]
        return [
            (dh, dw)
            for dh, dw in itertools.product(exprs, exprs)
            if all(
                dh.evaluate(inp, library) == out.height and dw.evaluate(inp, library) == out.width
                for inp, out in pairs
            )
        ]

    # -- assembly: read bodies x dims, verified against training --

    def _assemble(
        self,
        int_pool: list[Program],
        pairs: list[tuple[Grid, Grid]],
        task: Task,
        library: Library,
    ) -> SearchResult:
        dims = self._matching_dims(pairs, library)  # only dim pairs that yield the output shape
        candidates: list[Program] = [
            Apply("build_grid", (dh, dw, Lam(Lam(Apply("read", (Input(), row_expr, col_expr))))))
            for dh, dw in dims
            for row_expr, col_expr in itertools.product(int_pool, int_pool)
        ]
        # Cheapest-first, then return the first consistent one: that *is* the min-cost program
        # (Occam), and stopping there avoids verifying the whole space once a solution is found.
        candidates.sort(key=lambda p: self.cost.of(p, task, library))
        considered = 0
        for program in candidates:
            considered += 1
            try:
                if self.accepts(program, task, library):
                    return self._result(
                        strategy_extra={"pool": len(int_pool), "candidates": len(candidates)},
                        programs=(program,),
                        considered=considered,
                    )
            except Exception:  # out-of-bounds read etc. => discard candidate
                continue
        return self._result(
            strategy_extra={"pool": len(int_pool), "candidates": len(candidates)},
            programs=(),
            considered=considered,
        )

    def _result(
        self,
        *,
        strategy_extra: dict[str, int],
        programs: tuple[Program, ...],
        considered: int,
    ) -> SearchResult:
        stats = SearchStats(
            strategy="BuildGridSearch",
            considered=considered,
            returned=len(programs),
            extra=strategy_extra,
        )
        logger.info(stats.summary())
        return SearchResult(programs=programs, stats=stats)
