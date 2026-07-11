"""The bottom-up search engine (sections 4-5 of ARCHITECTURE.md).

A ``SearchEngine`` is frozen configuration: its capability policies and its ``Budget``. A single
``run`` builds the full typed pool bottom-up (``_enumerate``) and then reads solutions off it
(``extract``, §5.8). Per-run mutable scratch — the effort tally and the fresh-type-variable counter —
lives in ``_RunState`` so the engine itself stays immutable and reusable across runs.

The full §5 pipeline is in place on this spine: variadic composition (§5.2), higher-order fill and
lambda synthesis (§5.3), short-circuit ``If`` branching (§5.4), the polymorphism-instantiation
policy (§6.2), and memoized recursion (§9).
"""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from arc_lab.core.task import Task

from ..substrate.library import Library, Primitive, Value
from ..substrate.program import If, Lam, PrimRef, Program
from ..substrate.types import BOOL, COLOR, GRID, INT, ArrowType, Type, free_type_vars, instantiate
from .budget import Budget
from .composition import appfn_applications, applications
from .constraints import Constraint
from .context import Context
from .cost import Cost
from .extraction import extract
from .leaves import ConstantSource, seed_leaves
from .polymorphism import PolymorphismInstantiation, monotype_universe, resolve
from .pool import Pool
from .scope import Scope
from .search_result import SearchResult, SearchStats
from .signature import (
    Signature,
    combine_if_signature,
    compute_function_signature,
    compute_signature,
    peel_arrow,
    signature_matches_type,
)

FunctionHoleFillMode: TypeAlias = Literal["none", "point-free", "lambda-synthesis"]

#: The library's branching capability token (§5.4): its *presence* in the bag summons branching,
#: but the enumerator translates it into short-circuit ``If`` nodes — it is never applied eagerly.
_BRANCHING_ENTRY = "if"


@dataclass(slots=True)
class _Tally:
    """Search-effort counters, accumulated during a run and frozen into ``SearchStats``."""

    considered: int = 0
    errored: int = 0
    pruned: int = 0
    deduped: int = 0

    def as_extra(self) -> dict[str, int]:
        return {"errored": self.errored, "pruned": self.pruned, "deduped": self.deduped}


#: The memoization key of one ``_enumerate`` call (§9): exactly the inputs it is a pure function of.
#: ``goal_type``/``target`` belong to extraction and are deliberately absent.
_MemoKey: TypeAlias = "tuple[Scope, tuple[Context, ...], Budget]"


@dataclass(slots=True)
class _RunState:
    """The inputs and mutable scratch of a single ``run`` — never part of the memoization key (§9)."""

    task: Task
    library: Library
    cost: Cost
    universe: tuple[Type, ...] = ()  # the bounded-polymorphism monotype universe (§6.2)
    tally: _Tally = field(default_factory=_Tally)
    counter: itertools.count[int] = field(default_factory=itertools.count)
    #: Completed ``_enumerate`` pools by ``(scope, contexts, budget)``. Per-run (never on the
    #: engine), so the fixed ``task`` a ``body_sampler`` reads cannot leak across runs. Cached
    #: pools are treated as read-only by every caller.
    memo: dict[_MemoKey, Pool] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchEngine(ABC):
    """The reusable machinery that performs a program search."""

    @abstractmethod
    def run(
        self,
        *,
        task: Task,
        library: Library,
        constraints: tuple[Constraint, ...],
        cost: Cost,
    ) -> SearchResult:
        """Search for programs solving ``task``, ranked cheapest-first."""


@dataclass(frozen=True, slots=True, kw_only=True)
class BottomUpSearchEngine(SearchEngine):
    """Bottom-up enumeration: build the pool of well-typed terms round by round, deduped by behaviour."""

    constant_sources: tuple[ConstantSource, ...]
    function_hole_fill_mode: FunctionHoleFillMode
    polymorphism_instantiation: PolymorphismInstantiation
    budget: Budget
    #: Argument values sampled per parameter type when deduping a function value by behaviour (§8).
    #: The probe set is the cartesian product across parameters, so cost grows as size**arity.
    function_sample_size: int = 4

    def run(
        self,
        *,
        task: Task,
        library: Library,
        constraints: tuple[Constraint, ...],
        cost: Cost,
    ) -> SearchResult:
        train = [(ex.input, ex.output) for ex in task.train if ex.output is not None]
        contexts = tuple(Context(grid) for grid, _ in train)
        target: Signature = tuple(output for _, output in train)
        universe = (
            monotype_universe(library, self.budget.max_depth)
            if self.polymorphism_instantiation == "bounded"
            else ()
        )
        state = _RunState(task=task, library=library, cost=cost, universe=universe)

        pool = self._enumerate(Scope(()), contexts, self.budget, state)
        # ARC task outputs are grids; a general driver would derive the goal type from the task.
        solutions = extract(pool, GRID, target, constraints, task, library)

        return SearchResult(
            ranked_programs=solutions,
            stats=SearchStats(
                engine=type(self).__name__,
                considered=state.tally.considered,
                accepted=len(solutions),
                extra=state.tally.as_extra(),
            ),
        )

    def _enumerate(
        self,
        scope: Scope,
        contexts: tuple[Context, ...],
        budget: Budget,
        state: _RunState,
    ) -> Pool:
        """Build the full typed pool for ``(scope, contexts)`` up to ``budget`` (§5), memoized (§9).

        ``_enumerate`` is a pure function of ``(scope, contexts, budget)`` — no goal, no target, no
        early exit — so identical recursive sub-searches (the same lambda-body search recurring
        every composition round) are served from ``state.memo``.
        """
        key: _MemoKey = (scope, contexts, budget)
        cached = state.memo.get(key)
        if cached is not None:
            return cached
        pool = Pool()
        frontier: list[tuple[Program, Type]] = [
            *seed_leaves(scope, contexts, self.constant_sources),
            *self._function_leaves(state),
        ]
        for depth in range(budget.max_depth):
            branch_candidates: list[tuple[Program, Type, Signature | None]] = []
            if depth > 0:
                branch_candidates = self._branch_candidates(pool, state)
                frontier = list(self._compose(scope, pool, budget, state))
            self._absorb(frontier, contexts, pool, state)
            for program, vtype, signature in branch_candidates:
                self._absorb_one(program, vtype, vtype, signature, pool, state)
            pool = self._select_frontier(pool, budget)
        state.memo[key] = pool
        return pool

    def _compose(
        self, scope: Scope, pool: Pool, budget: Budget, state: _RunState
    ) -> Iterator[tuple[Program, Type]]:
        """One composition round: applications of every primitive, then the polymorphism policy (§6.2).

        Under ``unrestricted`` the pooled arguments may be polymorphic, so their types are
        re-instantiated with fresh vars per round (a no-op for the concrete pools of the other modes).
        Under ``lambda-synthesis``, each higher-order primitive with a ``body_sampler`` also
        contributes recursively-synthesized ``Lam`` values (§5.3) — pooled as first-class function
        values (§8) that fill its hole through ordinary composition in the next round.
        """
        policy = self.polymorphism_instantiation
        if policy == "unrestricted":
            candidates = [
                (program, instantiate(vtype, state.counter))
                for program, vtype in pool.typed_programs()
            ]
        else:
            candidates = list(pool.typed_programs())
        for primitive in state.library.primitives:
            if primitive.name == _BRANCHING_ENTRY:
                continue  # the branching token becomes If nodes (§5.4), never an eager Apply
            for program, result_type in applications(
                primitive, candidates, state.counter, budget.max_arity
            ):
                yield from resolve(program, result_type, policy, state.universe)
            if self.function_hole_fill_mode == "lambda-synthesis":
                yield from self._synthesized_lambdas(primitive, scope, budget, state)
        if self.function_hole_fill_mode != "none":  # apply pooled function values (§8)
            for program, result_type in appfn_applications(candidates, state.counter):
                yield from resolve(program, result_type, policy, state.universe)

    def _synthesized_lambdas(
        self, primitive: Primitive, scope: Scope, budget: Budget, state: _RunState
    ) -> Iterator[tuple[Program, Type]]:
        """Lambda synthesis (§5.3): recursively enumerate bodies for the primitive's arrow holes.

        For each *concrete* arrow-typed parameter of a primitive carrying a ``body_sampler``: peel
        the curried arrow into its binders and innermost result, recursively ``_enumerate`` the body
        in the extended scope against the sampler's contexts (one ``budget`` decrement for the whole
        peel, §4 — the termination guarantee), extract the bodies — just the target-matching ones
        under propagation, every typed body otherwise (§8) — and wrap them in nested ``Lam``\\ s. The
        value's type is the hole arrow itself, known here at construction (no ``Lam.result_type``).
        """
        if primitive.body_sampler is None:
            return
        for hole in primitive.param_types:
            if not isinstance(hole, ArrowType) or free_type_vars(hole):
                continue
            raw_contexts, raw_target = primitive.body_sampler(state.task, ())
            if not raw_contexts:
                continue
            body_contexts = tuple(Context(grid, binding) for grid, binding in raw_contexts)
            body_target: Signature | None = raw_target
            binders, body_type = peel_arrow(hole)
            body_scope = scope
            for binder in binders:
                body_scope = body_scope.extend(binder)
            body_pool = self._enumerate(body_scope, body_contexts, budget.descend(), state)
            for entry in body_pool.items_of_type(body_type):
                if body_target is not None and entry.sig != body_target:
                    continue
                lam: Program = entry.program
                for binder in reversed(binders):
                    lam = Lam(param_type=binder, body=lam)
                yield lam, hole

    def _function_leaves(self, state: _RunState) -> Iterator[tuple[Program, Type]]:
        """``PrimRef`` function-value leaves (§8): each primitive as a first-class value.

        Gated on the fill mode; a polymorphic primitive's arrow passes through the polymorphism
        policy like any composed result.
        """
        if self.function_hole_fill_mode == "none":
            return
        for primitive in state.library.primitives:
            if primitive.name == _BRANCHING_ENTRY:
                continue  # a PrimRef of the branching token would be applied eagerly — never minted
            arrow = ArrowType(primitive.param_types, primitive.return_type)
            yield from resolve(
                PrimRef(name=primitive.name), arrow, self.polymorphism_instantiation, state.universe
            )

    def _branch_candidates(
        self, pool: Pool, state: _RunState
    ) -> list[tuple[Program, Type, Signature | None]]:
        """Short-circuit ``If`` candidates for one round (§5.4), iff the library summons branching.

        Composed from a pooled ``BOOL`` condition and two distinct pooled same-typed branches; the
        signature is **combined from the parts' cached signatures** (never re-evaluated), which is
        inherently short-circuit — a partial branch (``⊥`` outside its selected region) still
        contributes, which is what makes domain-splitting ``if`` work. Function-typed branches are
        skipped: their signatures are sampled per argument tuple, not per context, so the per-context
        combination does not apply.
        """
        if _BRANCHING_ENTRY not in state.library:
            return []
        conditions = list(pool.items_of_type(BOOL))
        if not conditions:
            return []
        candidates: list[tuple[Program, Type, Signature | None]] = []
        for vtype in pool.types():
            if isinstance(vtype, ArrowType):
                continue
            entries = list(pool.items_of_type(vtype))
            for condition in conditions:
                for then, orelse in itertools.permutations(entries, 2):
                    program = If(cond=condition.program, then=then.program, orelse=orelse.program)
                    signature = combine_if_signature(condition.sig, then.sig, orelse.sig)
                    candidates.append((program, vtype, signature))
        return candidates

    def _absorb(
        self,
        candidates: list[tuple[Program, Type]],
        contexts: tuple[Context, ...],
        pool: Pool,
        state: _RunState,
    ) -> None:
        """Evaluate, prune (§5.6), and dedup each candidate. Value candidates go in first, then
        function candidates — whose signatures sample argument values from the now-populated pool (§8).
        """
        functions: list[tuple[Program, ArrowType]] = []
        for program, vtype in candidates:
            if isinstance(vtype, ArrowType):
                functions.append((program, vtype))
            else:
                signature = compute_signature(program, contexts, state.library)
                self._absorb_one(program, vtype, vtype, signature, pool, state)
        if functions:
            arg_samples = self._argument_samples(functions, contexts, pool, state)
            for program, arrow in functions:
                signature = compute_function_signature(
                    program, arrow, contexts, arg_samples, state.library
                )
                _, result_type = peel_arrow(arrow)
                self._absorb_one(program, arrow, result_type, signature, pool, state)

    def _absorb_one(
        self,
        program: Program,
        vtype: Type,
        output_type: Type,
        signature: Signature | None,
        pool: Pool,
        state: _RunState,
    ) -> None:
        """Prune (fully-undefined or a *concrete* output-type mismatch) and dedup one candidate.

        ``output_type`` is what the signature's values inhabit — ``vtype`` for a value program, the
        function's ultimate result for a function value. A *polymorphic* output type is not pruned (its
        free vars match any value); the pool keys on ``vtype``.
        """
        state.tally.considered += 1
        if signature is None:
            state.tally.errored += 1
            return
        if not free_type_vars(output_type) and not signature_matches_type(signature, output_type):
            state.tally.pruned += 1
            return
        cost = state.cost.of(program, state.task, state.library)
        if not pool.add_dedup(vtype, signature, program, cost):
            state.tally.deduped += 1

    def _argument_samples(
        self,
        functions: list[tuple[Program, ArrowType]],
        contexts: tuple[Context, ...],
        pool: Pool,
        state: _RunState,
    ) -> dict[Type, Sequence[Value]]:
        """A bounded sample of argument values per parameter type demanded by the function candidates."""
        needed: set[Type] = set()
        for _, arrow in functions:
            params, _ = peel_arrow(arrow)
            needed.update(params)
        reference = contexts[0] if contexts else None
        return {vtype: self._sample_type(vtype, pool, reference, state) for vtype in needed}

    def _sample_type(
        self, vtype: Type, pool: Pool, reference: Context | None, state: _RunState
    ) -> Sequence[Value]:
        """Sampled values of ``vtype``: fixed small sets for base types, pooled values otherwise."""
        size = self.function_sample_size
        if vtype in (INT, COLOR):
            return list(range(size))
        if vtype == BOOL:
            return [False, True]
        if reference is None:
            return []
        values: list[Value] = []
        for program in pool.of_type(vtype):
            try:
                values.append(
                    program.evaluate(reference.input_grid, state.library, scope=reference.scope_binding)
                )
            except Exception:  # a program that errors at the reference context yields no sample
                continue
            if len(values) >= size:
                break
        return values

    def _select_frontier(self, pool: Pool, budget: Budget) -> Pool:
        """Keep the cheapest ``budget.max_pool`` entries to carry into the next round (§5.7)."""
        return pool.cheapest(budget.max_pool)


@dataclass(frozen=True, slots=True, kw_only=True)
class BeamBottomUpSearchEngine(BottomUpSearchEngine):
    """Bottom-up enumeration with a fixed beam: keep only the cheapest ``beam_width`` per round."""

    beam_width: int

    def _select_frontier(self, pool: Pool, budget: Budget) -> Pool:
        return pool.cheapest(self.beam_width)
