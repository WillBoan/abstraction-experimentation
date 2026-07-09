"""Generic open-term search for ``build_grid`` programs with per-cell decision bodies.

``BuildGridSearch`` is the specialized geometry engine: it searches coordinate expressions and then
assembles ``read(input, row, col)`` bodies. This search is the complete-floor counterpart: it
enumerates a *typed open body* over the cell scope itself, so a program can branch on per-cell
observations such as ``if(eq(read(...), color), a, b)``.

The search is still intentionally narrow:

* dimensions are synthesized as closed ``INT`` programs over the input;
* the cell body is synthesized as an open ``COLOR`` program over ``$1`` = row and ``$0`` = col;
* both layers use the same type-directed composition helper as the generic enumerator, so
  first-order polymorphism (``eq`` / ``if``) works uniformly.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

import numpy as np

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search.base import Search, SearchResult, SearchStats
from arc_lab.solvers.dsl.search.cost import Cost, ProgramSize
from arc_lab.solvers.dsl.search.type_directed import (
    TypedProgram,
    candidate_applications,
    signature_matches_type,
)
from arc_lab.solvers.dsl.substrate.library import Library, Primitive, Value
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Input, Lam, Program, Var
from arc_lab.solvers.dsl.substrate.types import BOOL, COLOR, GRID, INT, Type, free_type_vars

_Signature: TypeAlias = "tuple[Value, ...]"
_BodyPoint: TypeAlias = "tuple[Grid, int, int]"
_ResultTargetPolicy: TypeAlias = "Callable[[Primitive], tuple[Type, ...] | None]"


class BuildGridBodySearch(Search):
    """Find a ``build_grid`` program whose body is a typed open ``COLOR`` term."""

    def __init__(
        self,
        *,
        cost: Cost | None = None,
        max_dim_depth: int = 1,
        # The per-round, per-type beam. A polymorphic floor (``eq`` / ``if``) makes each round cost
        # ~O(beam^2) in the worst case, so the default is a *minimum generally useful* value (enough to
        # solve a basic size-general mask), not a research-grade budget — a forgotten override should
        # fail fast/cheap, not silently blow up. Harder tasks pass a larger ``beam_width`` explicitly.
        max_body_depth: int = 3,
        beam_width: int = 32,
        max_pool: int = 600,
        int_consts: tuple[int, ...] = (0, 1),
        body_polymorphic_return_targets: tuple[Type, ...] = (COLOR,),
    ) -> None:
        super().__init__()
        self.cost = ProgramSize() if cost is None else cost
        self.max_dim_depth = max_dim_depth
        self.max_body_depth = max_body_depth
        self.beam_width = beam_width
        self.max_pool = max_pool
        self.int_consts = int_consts
        self.body_polymorphic_return_targets = body_polymorphic_return_targets

    def find(self, task: Task, library: Library) -> SearchResult:
        pairs = [(ex.input, ex.output) for ex in task.train if ex.output is not None]
        if len(pairs) != len(task.train):
            return self._result(programs=(), considered=0, extra={})

        dim_pools, dim_considered = self._enumerate_terms(
            task,
            library,
            leaves=self._closed_leaves(task),
            max_depth=self.max_dim_depth,
            signature_of=lambda program: self._closed_signature(program, pairs, library),
            result_targets=self._dim_result_targets,
        )
        target_height = tuple(out.height for _, out in pairs)
        target_width = tuple(out.width for _, out in pairs)
        height_program = dim_pools.get(INT, {}).get(target_height)
        width_program = dim_pools.get(INT, {}).get(target_width)
        if height_program is None or width_program is None:
            return self._result(
                programs=(),
                considered=dim_considered,
                extra={"dim_pool": len(dim_pools.get(INT, {})), "body_pool": 0},
            )

        body_points = [
            (inp, i, j) for inp, out in pairs for i in range(out.height) for j in range(out.width)
        ]
        target_body = tuple(
            int(out[i, j])
            for inp, out in pairs
            for i in range(out.height)
            for j in range(out.width)
        )
        body_pools, body_considered = self._enumerate_terms(
            task,
            library,
            leaves=self._open_body_leaves(task),
            max_depth=self.max_body_depth,
            signature_of=lambda program: self._body_signature(program, body_points, library),
            result_targets=self._body_result_targets,
        )
        body_program = body_pools.get(COLOR, {}).get(target_body)
        if body_program is None:
            return self._result(
                programs=(),
                considered=dim_considered + body_considered,
                extra={
                    "dim_pool": len(dim_pools.get(INT, {})),
                    "body_pool": len(body_pools.get(COLOR, {})),
                },
            )

        program = Apply("build_grid", (height_program, width_program, Lam(Lam(body_program))))
        programs = (program,) if self.accepts(program, task, library) else ()
        return self._result(
            programs=programs,
            considered=dim_considered + body_considered + 1,
            extra={
                "dim_pool": len(dim_pools.get(INT, {})),
                "body_pool": len(body_pools.get(COLOR, {})),
            },
        )

    def _enumerate_terms(
        self,
        task: Task,
        library: Library,
        *,
        leaves: list[TypedProgram],
        max_depth: int,
        signature_of: Callable[[Program], _Signature | None],
        result_targets: _ResultTargetPolicy | None = None,
    ) -> tuple[dict[Type, dict[_Signature, Program]], int]:
        pools: dict[Type, dict[_Signature, Program]] = {}
        considered = 0

        def consider(program: Program, expected: Type) -> None:
            nonlocal considered
            considered += 1
            signature = signature_of(program)
            if signature is None or not signature_matches_type(signature, expected):
                return
            bucket = pools.setdefault(expected, {})
            existing = bucket.get(signature)
            if existing is None or program.size() < existing.size():
                bucket[signature] = program

        for leaf, leaf_type in leaves:
            consider(leaf, leaf_type)

        fixed = [prim for prim in library.primitives if not prim.is_variadic]
        for _ in range(max_depth):
            frozen = {
                value_type: sorted(
                    bucket.values(),
                    key=lambda program: self.cost.of(program, task, library),
                )[: self.beam_width]
                for value_type, bucket in pools.items()
            }
            value_candidates: list[TypedProgram] = [
                (program, value_type)
                for value_type, programs in frozen.items()
                for program in programs
            ]
            for prim in fixed:
                targets = None if result_targets is None else result_targets(prim)
                if targets is None:
                    applications = candidate_applications(prim, value_candidates=value_candidates)
                    for args, result_type in applications:
                        consider(Apply(prim.name, args), result_type)
                    continue
                for target in targets:
                    for args, result_type in candidate_applications(
                        prim,
                        value_candidates=value_candidates,
                        result_targets=(target,),
                    ):
                        consider(Apply(prim.name, args), result_type)
            if sum(len(bucket) for bucket in pools.values()) > self.max_pool:
                break

        return pools, considered

    @staticmethod
    def _dim_result_targets(prim: Primitive) -> tuple[Type, ...] | None:
        return (INT,) if free_type_vars(prim.return_type) else None

    def _body_result_targets(self, prim: Primitive) -> tuple[Type, ...] | None:
        return self.body_polymorphic_return_targets if free_type_vars(prim.return_type) else None

    def _closed_leaves(self, task: Task) -> list[TypedProgram]:
        colors = sorted({int(c) for ex in task.train for c in np.unique(ex.input.array)})
        colors += sorted(
            {
                int(c)
                for ex in task.train
                if ex.output is not None
                for c in np.unique(ex.output.array)
            }
        )
        unique_colors = sorted(set(colors))
        leaves: list[TypedProgram] = [(Input(), GRID)]
        leaves.extend((Const(color, COLOR), COLOR) for color in unique_colors)
        leaves.extend((Const(value, INT), INT) for value in self.int_consts)
        leaves.extend(((Const(False, BOOL), BOOL), (Const(True, BOOL), BOOL)))
        return leaves

    def _open_body_leaves(self, task: Task) -> list[TypedProgram]:
        return [
            *self._closed_leaves(task),
            (Var(0, INT), INT),
            (Var(1, INT), INT),
        ]

    def _closed_signature(
        self,
        program: Program,
        pairs: list[tuple[Grid, Grid]],
        library: Library,
    ) -> _Signature | None:
        try:
            return tuple(program.evaluate(inp, library) for inp, _ in pairs)
        except Exception:
            return None

    def _body_signature(
        self,
        program: Program,
        points: list[_BodyPoint],
        library: Library,
    ) -> _Signature | None:
        try:
            return tuple(program.evaluate(inp, library, (), (row, col)) for inp, row, col in points)
        except Exception:
            return None

    def _result(
        self,
        *,
        programs: tuple[Program, ...],
        considered: int,
        extra: dict[str, int],
    ) -> SearchResult:
        stats = SearchStats(
            strategy="BuildGridBodySearch",
            considered=considered,
            returned=len(programs),
            extra=extra,
        )
        return SearchResult(programs=programs, stats=stats)
