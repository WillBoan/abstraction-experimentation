"""The bottom-up search engine (sections 4-5 of ARCHITECTURE.md).

A ``SearchEngine`` is frozen configuration: its capability policies and its ``Budget``. A single
``run`` builds the full typed pool bottom-up (``_enumerate``) and then reads solutions off it
(``extract``, §5.8). Per-run mutable scratch — the capability tracker (``search/tracking.py``) and
the fresh-type-variable counter — lives in ``_RunState`` so the engine itself stays immutable and
reusable across runs.

The full §5 pipeline is in place on this spine: variadic composition (§5.2), higher-order fill and
lambda synthesis (§5.3), short-circuit ``If`` branching (§5.4), the polymorphism-instantiation
policy (§6.2), and memoized recursion (§9).
"""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from arc_lab.core.task import TrainExamples, train_with_output

from ..substrate.library import EnclosingTarget, Library, Primitive, Value
from ..substrate.program import If, Lam, PrimRef, Program
from ..substrate.types import (
    BOOL,
    COLOR,
    GRID,
    INT,
    ArrowType,
    Type,
    apply_subst,
    free_type_vars,
    instantiate,
    unify,
)
from .budget import Budget
from .composition import appfn_applications, applications, hole_assignments
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
from .tracking import Outcome, SearchTracker, primitive_keys

FunctionHoleFillMode: TypeAlias = Literal["none", "point-free", "lambda-synthesis"]

#: How an arrow-hole type variable left unpinned by every sibling (§5.3's ``hole_assignments``) gets
#: resolved — orthogonal to ``PolymorphismInstantiation`` (that governs ordinary composed *values*;
#: this governs a lambda *binder's* type, with a different cost character: an eager grounding here
#: triggers a full recursive body search per candidate type, not an O(1) substitution).
#: ``reject``: skip synthesis for that hole (today's implicit behavior). ``eager_grounding_over_
#: universe``: try each type in the run's bounded monotype universe. ``lazy_synthesis``: true
#: deferred/lazy resolution (what ``unrestricted`` actually means elsewhere — pool a canonicalized,
#: unsearched placeholder, resolve on demand) — not yet built; ``BottomUpSearchEngine.__post_init__``
#: rejects it whenever it would actually be reached.
UnpinnedTypeVarMode: TypeAlias = Literal[
    "reject", "eager_grounding_over_universe", "lazy_synthesis"
]

#: The library's branching capability token (§5.4): its *presence* in the bag summons branching,
#: but the enumerator translates it into short-circuit ``If`` nodes — it is never applied eagerly.
_BRANCHING_ENTRY = "if"


def _uses_new_layer(program: Program, new_layer: frozenset[int]) -> bool:
    """Whether a freshly-composed ``program`` uses at least one argument from the previous round's
    additions (the new-layer restriction, §5.2). ``new_layer`` holds the ``id()`` of the pooled
    programs added last round; a composed node's direct ``children`` are exactly the pooled argument
    programs it was built from (the same objects), so identity membership is exact — and every
    object compared is a live pool program at this point, so no ``id`` can alias a freed one.

    Completeness: any program first constructible this round has a direct child of the previous
    round's depth, so this never filters out a genuinely new combination — only re-derivations of
    programs an earlier round already built.
    """
    return any(id(child) in new_layer for child in program.children())


def derive_goal_type(train_examples: TrainExamples) -> Type:
    """Derive the run's goal type from the task data — not yet built.

    ``Example.output: Grid | None`` (``core/task.py``) makes ``GRID`` the *only* value any derivation
    could produce for this codebase's ``Task`` model — there is nothing else to derive until
    ``Task``/``Example`` become generic over output type, a separate, foundational change touching
    dataset loading/``eval``/``viz``/scoring. This function exists so that gap is visible and named
    (``BottomUpSearchEngine.run``'s ``goal_type`` param routes here when explicitly passed ``None``)
    rather than silently absent — it is not a sign the capability is imminent.
    """
    raise NotImplementedError(
        "goal-type derivation from the task is not yet built; pass goal_type explicitly "
        "(BottomUpSearchEngine.run defaults it to GRID)"
    )


#: The memoization key of one ``_enumerate`` call (§9): exactly the inputs it is a pure function of.
#: The top-level ``goal_type``/``target`` stay out (they belong to extraction) — but
#: ``enclosing_target`` (the recursively-threaded local target lambda synthesis consults, §7) *is*
#: part of a sub-search's identity and must be in the key: it can change how many candidates get
#: synthesized and absorbed into *this* call's own pool (propagation vs. baseline), so two different
#: recursion paths that happen to reach the same ``(scope, contexts, budget)`` with a different
#: ``enclosing_target`` are genuinely different searches, not a cache hit. (Concretely: two distinct
#: primitives peeling to the same body scope could coincidentally produce identical body contexts
#: while deriving different targets — memoizing on `enclosing_target` too is what keeps that sound.)
_MemoKey: TypeAlias = "tuple[Scope, tuple[Context, ...], Budget, EnclosingTarget | None]"


@dataclass(slots=True)
class _RunState:
    """The inputs and mutable scratch of a single ``run`` — never part of the memoization key (§9)."""

    train_examples: TrainExamples
    library: Library
    cost: Cost
    goal_type: Type = GRID
    #: The training outputs, index-aligned with ``train_with_output(train_examples)`` — the values
    #: half of the top-level ``EnclosingTarget`` (§7); ``()`` if there are none.
    train_target: tuple[Value, ...] = ()
    universe: tuple[Type, ...] = ()  # the bounded-polymorphism monotype universe (§6.2)
    tracker: SearchTracker = field(default_factory=SearchTracker)
    counter: itertools.count[int] = field(default_factory=itertools.count)
    #: Completed ``_enumerate`` pools by ``(scope, contexts, budget, enclosing_target)``. Per-run
    #: (never on the engine), so the fixed ``train_examples`` a ``body_sampler`` reads cannot leak
    #: across runs. Cached pools are treated as read-only by every caller.
    memo: dict[_MemoKey, Pool] = field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class SearchEngine(ABC):
    """The reusable machinery that performs a program search.

    ``run`` takes the task's **train examples only** (never the full ``Task``), so
    blindness to test examples is structural, not a promise (EXECUTION.md).
    """

    @abstractmethod
    def run(
        self,
        *,
        train_examples: TrainExamples,
        library: Library,
        constraints: tuple[Constraint, ...],
        cost: Cost,
        budget: Budget,
        goal_type: Type | None = GRID,
        tracker: SearchTracker | None = None,
    ) -> SearchResult:
        """Search for programs consistent with ``train_examples``, ranked cheapest-first.

        ``budget`` is an argument, not an engine field: the engine is *machinery* (the
        algorithm and its capability policies — HOW to search); the budget is per-run
        *data* (HOW MUCH resource), varied independently of the engine — e.g. across a
        study grid's cells. It lives on ``Config`` alongside library/constraints/cost.

        ``goal_type`` defaults to ``GRID`` (the only value any real derivation could
        produce today) but is explicit and overridable; pass ``None`` to route through
        ``derive_goal_type`` instead — currently unbuilt (raises), so the capability gap
        is visible rather than silently absent.

        ``tracker`` is likewise a per-run argument, not engine state: pass a pre-configured
        ``SearchTracker`` (sampling / full capture attached by ``execute()``, from a
        ``TraceSpec`` — outside run identity, since telemetry never changes *what* is
        computed) to observe this run; omit it for a fresh, unconfigured one (the always-on
        outcome counts still accumulate — only sampling/capture are opt-in).
        """


@dataclass(frozen=True, slots=True, kw_only=True)
class BottomUpSearchEngine(SearchEngine):
    """Bottom-up enumeration: build the pool of well-typed terms round by round, deduped by behaviour."""

    constant_sources: tuple[ConstantSource, ...]
    function_hole_fill_mode: FunctionHoleFillMode
    polymorphism_instantiation: PolymorphismInstantiation
    unpinned_type_var_mode: UnpinnedTypeVarMode
    #: Argument values sampled per parameter type when deduping a function value by behaviour (§8).
    #: The probe set is the cartesian product across parameters, so cost grows as size**arity.
    function_sample_size: int = 4
    #: Whether to invert a wrapping primitive's target to seed a nested HOF hole's search (e.g.
    #: propagating through a future `render`) — a distinct search-strategy dimension (a goal-seeded
    #: pass alongside bottom-up composition, needing a new `inverse_semantics` primitive capability),
    #: not a bigger version of `enclosing_target` propagation. Named in MACHINERY.md's lever-map
    #: ("Bidirectional", `unbuilt`) but not committed to this overhaul. Not yet built: `True` raises
    #: in `__post_init__`, so the gap is visible rather than silently absent.
    inverse_semantics_propagation: bool = False

    def __post_init__(self) -> None:
        if self.inverse_semantics_propagation:
            raise NotImplementedError(
                "inverse-semantics propagation is not yet built — see MACHINERY.md's "
                "'Bidirectional' row"
            )
        if (
            self.unpinned_type_var_mode == "lazy_synthesis"
            and self.function_hole_fill_mode == "lambda-synthesis"
        ):
            raise NotImplementedError(
                "lazy_synthesis (true deferred lambda-hole resolution) is not yet built"
            )
        if self.function_sample_size < 1:
            raise ValueError(f"function_sample_size must be >= 1, got {self.function_sample_size}")

    def run(
        self,
        *,
        train_examples: TrainExamples,
        library: Library,
        constraints: tuple[Constraint, ...],
        cost: Cost,
        budget: Budget,
        goal_type: Type | None = GRID,
        tracker: SearchTracker | None = None,
    ) -> SearchResult:
        # goal_type=None only fires the not-yet-built derivation path (see derive_goal_type) —
        # GRID is the only goal type this codebase's Task model can currently produce.
        resolved_goal_type = (
            goal_type if goal_type is not None else derive_goal_type(train_examples)
        )
        # The redundant `if` restores mypy's flow-narrowing of `ex.output` — train_with_output's
        # filter isn't visible to the type checker across the function call boundary.
        train = [
            (ex.input, ex.output)
            for ex in train_with_output(train_examples)
            if ex.output is not None
        ]
        contexts = tuple(Context(grid) for grid, _ in train)
        # Same values, two roles: `target` (Signature, allows Bottom) is the goal-test comparison;
        # `train_target` (concrete Value) feeds enclosing-target propagation for hole-filling.
        target: Signature = tuple(output for _, output in train)
        train_target: tuple[Value, ...] = tuple(output for _, output in train)

        universe = (
            monotype_universe(library, budget.max_depth)
            if self.polymorphism_instantiation == "bounded"
            or self.unpinned_type_var_mode == "eager_grounding_over_universe"
            else ()
        )
        state = _RunState(
            train_examples=train_examples,
            library=library,
            cost=cost,
            goal_type=resolved_goal_type,
            train_target=train_target,
            universe=universe,
            tracker=tracker if tracker is not None else SearchTracker(),
        )
        top_target = EnclosingTarget(train_target, resolved_goal_type) if train_target else None

        pool = self._enumerate(Scope(()), contexts, budget, state, top_target, top_level=True)
        extraction = extract(pool, resolved_goal_type, target, constraints, train_examples, library)
        for entry in extraction.accepted:
            state.tracker.record(
                entry.candidate_index, entry.program, entry.primitives, Outcome.ACCEPTED
            )
        for entry in extraction.constraint_rejected:
            state.tracker.record(
                entry.candidate_index, entry.program, entry.primitives, Outcome.CONSTRAINT_REJECTED
            )
        for vtype, entry in pool.entries():
            if vtype == resolved_goal_type and entry.sig == target:
                continue  # already accounted for above (accepted or constraint_rejected)
            state.tracker.record(
                entry.candidate_index, entry.program, entry.primitives, Outcome.GOAL_UNMATCHED
            )
        solutions = tuple(entry.program for entry in extraction.accepted)

        return SearchResult(
            ranked_programs=solutions,
            stats=SearchStats(
                engine=type(self).__name__,
                considered=state.tracker.considered,
                accepted=len(solutions),
                outcomes=state.tracker.totals(),
                by_primitive=state.tracker.by_primitive(),
            ),
        )

    def _enumerate(
        self,
        scope: Scope,
        contexts: tuple[Context, ...],
        budget: Budget,
        state: _RunState,
        enclosing_target: EnclosingTarget | None,
        *,
        top_level: bool = False,
    ) -> Pool:
        """Build the full typed pool for ``(scope, contexts, enclosing_target)`` up to ``budget``
        (§5), memoized (§9 — see ``_MemoKey`` on why ``enclosing_target`` is part of the key).

        ``top_level`` marks the one call ``run()`` makes directly (as opposed to a lambda-synthesis
        sub-search, §5.3): a sub-search's pool never faces the top-level goal test, so its
        survivors finalize as ``GOAL_UNMATCHED`` right here, once, the moment the pool is first
        computed (never on a memo cache hit). The top-level pool's finalization is deferred to
        ``run()``, after ``extract()`` classifies it.
        """
        key: _MemoKey = (scope, contexts, budget, enclosing_target)
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
                # The new-layer restriction (§5.2): compose only over combinations that use at least
                # one argument added in the previous round (``generation == depth - 1``), so a
                # lower-depth program is built once at its own depth, not regenerated-and-deduped
                # every round. At depth 1 this is a no-op (the whole pool is the leaf layer).
                new_layer = frozenset(
                    id(entry.program)
                    for _, entry in pool.entries()
                    if entry.generation == depth - 1
                )
                branch_candidates = self._branch_candidates(pool, state, new_layer)
                frontier = list(
                    self._compose(scope, contexts, pool, budget, state, enclosing_target, new_layer)
                )
            # Every pooled value program's (non-function) signature, by identity — the composed-
            # signature fast path (``compute_signature``'s ``child_signatures``): a fresh ``Apply``'s
            # direct children are exactly these pool objects (§5.2), so their per-context values are
            # already known and never need re-``evaluate``. Function-typed entries are excluded: their
            # cached signature is an argument-sampled behavioural fingerprint (``compute_function_
            # signature``), not a raw per-context value, so a lookup miss there correctly falls back.
            child_signatures = {
                id(entry.program): entry.sig
                for vtype, entry in pool.entries()
                if not isinstance(vtype, ArrowType)
            }
            self._absorb(frontier, contexts, pool, state, depth, child_signatures)
            for program, vtype, signature in branch_candidates:
                self._absorb_one(program, vtype, vtype, signature, pool, state, depth)
            pool = self._select_frontier(pool, budget, state)
        state.memo[key] = pool
        if not top_level:
            for _, entry in pool.entries():
                state.tracker.record(
                    entry.candidate_index, entry.program, entry.primitives, Outcome.GOAL_UNMATCHED
                )
        return pool

    def _compose(
        self,
        scope: Scope,
        contexts: tuple[Context, ...],
        pool: Pool,
        budget: Budget,
        state: _RunState,
        enclosing_target: EnclosingTarget | None,
        new_layer: frozenset[int],
    ) -> Iterator[tuple[Program, Type]]:
        """One composition round: applications of every primitive, then the polymorphism policy (§6.2).

        Under ``unrestricted`` the pooled arguments may be polymorphic, so their types are
        re-instantiated with fresh vars per round (a no-op for the concrete pools of the other modes).
        Under ``lambda-synthesis``, each higher-order primitive with a ``body_sampler`` also
        contributes recursively-synthesized ``Lam`` values (§5.3) — pooled as first-class function
        values (§8) that fill its hole through ordinary composition in the next round.

        ``new_layer`` holds the identities of the pooled programs added last round; the new-layer
        restriction keeps only compositions that use at least one of them (``_uses_new_layer``), so
        combinations already built in an earlier round are not regenerated. Synthesized lambdas are
        exempt: their body comes from a nested sub-search's pool, not this scope's, so their children
        are never in ``new_layer`` — they are (correctly) re-offered each round.
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
                if _uses_new_layer(program, new_layer):
                    yield from resolve(program, result_type, policy, state.universe)
            if self.function_hole_fill_mode == "lambda-synthesis":
                yield from self._synthesized_lambdas(
                    primitive, scope, contexts, candidates, budget, state, enclosing_target
                )
        if self.function_hole_fill_mode != "none":  # apply pooled function values (§8)
            for program, result_type in appfn_applications(candidates, state.counter):
                if _uses_new_layer(program, new_layer):
                    yield from resolve(program, result_type, policy, state.universe)

    def _synthesized_lambdas(
        self,
        primitive: Primitive,
        scope: Scope,
        contexts: tuple[Context, ...],
        candidates: Sequence[tuple[Program, Type]],
        budget: Budget,
        state: _RunState,
        enclosing_target: EnclosingTarget | None,
    ) -> Iterator[tuple[Program, Type]]:
        """Lambda synthesis (§5.3): recursively enumerate bodies for the primitive's arrow holes.

        A *concrete* arrow-typed hole (no free type vars — e.g. ``build_grid``) is already fully
        typed by the primitive's own signature; a hole with free type vars (e.g. ``map``'s ``a→b``)
        is pinned by unifying against sibling arguments that share those variables
        (``hole_assignments``, §5.2-style), with any variable that stays unpinned resolved per
        ``unpinned_type_var_mode``. Either way, the resolved hole and the (possibly empty) sibling
        values feed the shared ``_synthesize_for_hole``.
        """
        if primitive.body_sampler is None:
            return
        for hole_index, hole in enumerate(primitive.param_types):
            if not isinstance(hole, ArrowType):
                continue
            if not free_type_vars(hole):
                yield from self._synthesize_for_hole(
                    primitive,
                    hole,
                    primitive.return_type,
                    (),
                    scope,
                    budget,
                    state,
                    enclosing_target,
                )
                continue
            for sibling_programs, instantiated_hole, return_type in hole_assignments(
                primitive, hole_index, candidates, state.counter
            ):
                assert isinstance(instantiated_hole, ArrowType)
                if free_type_vars(instantiated_hole) or free_type_vars(return_type):
                    for grounded_hole, grounded_return in self._ground_unpinned_hole(
                        instantiated_hole, return_type, state
                    ):
                        sibling_values = self._evaluate_siblings(sibling_programs, contexts, state)
                        if sibling_values is None:
                            continue
                        yield from self._synthesize_for_hole(
                            primitive,
                            grounded_hole,
                            grounded_return,
                            sibling_values,
                            scope,
                            budget,
                            state,
                            enclosing_target,
                        )
                    continue
                sibling_values = self._evaluate_siblings(sibling_programs, contexts, state)
                if sibling_values is None:
                    continue
                yield from self._synthesize_for_hole(
                    primitive,
                    instantiated_hole,
                    return_type,
                    sibling_values,
                    scope,
                    budget,
                    state,
                    enclosing_target,
                )

    def _ground_unpinned_hole(
        self, hole: ArrowType, return_type: Type, state: _RunState
    ) -> Iterator[tuple[ArrowType, Type]]:
        """Resolve a hole's (and its primitive's return type's) still-free type variables per
        ``unpinned_type_var_mode`` (decision 3) — the same substitution applied to both, since they
        may share a variable (``map``'s hole ``a→b`` and its ``List[b]`` return type both use ``b``).

        ``reject``: nothing (no synthesis for this hole). ``eager_grounding_over_universe``: every
        grounding of the free variables over ``state.universe`` (each triggers its own full
        recursive body search in the caller — costlier per-candidate than ordinary ``bounded``
        composition's O(1) substitution). ``lazy_synthesis`` never reaches here (rejected at
        construction, ``__post_init__``, whenever it could).
        """
        if self.unpinned_type_var_mode != "eager_grounding_over_universe":
            return
        free = sorted(free_type_vars(hole) | free_type_vars(return_type))
        for grounding in itertools.product(state.universe, repeat=len(free)):
            subst = dict(zip(free, grounding, strict=True))
            resolved_hole = apply_subst(subst, hole)
            resolved_return = apply_subst(subst, return_type)
            assert isinstance(resolved_hole, ArrowType)
            if not free_type_vars(resolved_hole) and not free_type_vars(resolved_return):
                yield resolved_hole, resolved_return

    def _evaluate_siblings(
        self, programs: tuple[Program, ...], contexts: tuple[Context, ...], state: _RunState
    ) -> tuple[tuple[Value, ...] | None, ...] | None:
        """Evaluate sibling-argument programs at every context: one entry per
        context, ``None`` where a sibling errored *at that context* — mirroring how a partial
        signature stays pooled elsewhere (§5.5), so a sibling total on most-but-not-all training
        contexts can still seed synthesis from the contexts it *is* defined on. Returns ``None``
        (skip entirely) only if every context is undefined, mirroring ``compute_signature``.
        """
        rows: list[tuple[Value, ...] | None] = []
        for context in contexts:
            try:
                rows.append(
                    tuple(
                        program.evaluate(
                            context.input_grid, state.library, scope=context.scope_binding
                        )
                        for program in programs
                    )
                )
            except Exception:
                rows.append(None)
        if all(row is None for row in rows):
            return None
        return tuple(rows)

    def _synthesize_for_hole(
        self,
        primitive: Primitive,
        hole: ArrowType,
        return_type: Type,
        sibling_values: tuple[tuple[Value, ...] | None, ...],
        scope: Scope,
        budget: Budget,
        state: _RunState,
        enclosing_target: EnclosingTarget | None,
    ) -> Iterator[tuple[Program, Type]]:
        """Recursively search bodies for one (fully-resolved, possibly sibling-pinned) arrow hole
        and wrap them in nested ``Lam``\\ s (§5.3). ``sibling_values`` is ``()`` for a hole concrete
        from the primitive's own signature (``build_grid``); otherwise one value-tuple-or-``None``
        per context, from ``_evaluate_siblings``. ``return_type`` is the primitive's return type
        after whatever substitution resolved ``hole`` (they can share a type variable, e.g.
        ``map``'s ``b``). Every caller guarantees ``hole`` has no free type variables by this point
        — concrete from the start, sibling-pinned, or resolved by ``_ground_unpinned_hole`` — so its
        peeled binders and result type are already fully known; there is nothing left to search for.

        The primitive may consult ``enclosing_target`` (§7/§8) only if ``return_type`` unifies with
        the target's type — checked here, once, rather than trusted to the sampler. ``unify`` can
        succeed with an *empty* substitution (e.g. ``GRID`` unifying with ``GRID``), so the check is
        ``is not None``, not truthiness.
        """
        assert primitive.body_sampler is not None
        local_target = (
            enclosing_target
            if enclosing_target is not None
            and unify(return_type, enclosing_target.value_type) is not None
            else None
        )
        raw_contexts, raw_target = primitive.body_sampler(
            state.train_examples, sibling_values, local_target
        )
        if not raw_contexts:
            return
        body_contexts = tuple(Context(grid, binding) for grid, binding in raw_contexts)
        body_target: Signature | None = raw_target
        binders, body_type = peel_arrow(hole)
        body_scope = scope
        for binder in binders:
            body_scope = body_scope.extend(binder)
        child_target = EnclosingTarget(raw_target, body_type) if raw_target is not None else None
        body_pool = self._enumerate(
            body_scope, body_contexts, budget.descend(), state, child_target
        )
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
        self, pool: Pool, state: _RunState, new_layer: frozenset[int]
    ) -> list[tuple[Program, Type, Signature | None]]:
        """Short-circuit ``If`` candidates for one round (§5.4), iff the library summons branching.

        Composed from a pooled ``BOOL`` condition and two distinct pooled same-typed branches; the
        signature is **combined from the parts' cached signatures** (never re-evaluated), which is
        inherently short-circuit — a partial branch (``⊥`` outside its selected region) still
        contributes, which is what makes domain-splitting ``if`` work. Function-typed branches are
        skipped: their signatures are sampled per argument tuple, not per context, so the per-context
        combination does not apply. The new-layer restriction applies as it does to composition: at
        least one of the condition/branches must be from the previous round (``_uses_new_layer``).
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
                    if not _uses_new_layer(program, new_layer):
                        continue
                    signature = combine_if_signature(condition.sig, then.sig, orelse.sig)
                    candidates.append((program, vtype, signature))
        return candidates

    def _absorb(
        self,
        candidates: list[tuple[Program, Type]],
        contexts: tuple[Context, ...],
        pool: Pool,
        state: _RunState,
        generation: int,
        child_signatures: Mapping[int, Signature],
    ) -> None:
        """Evaluate, prune (§5.6), and dedup each candidate. Value candidates go in first, then
        function candidates — whose signatures sample argument values from the now-populated pool (§8).

        ``generation`` is the composition round these candidates belong to, stamped on every pooled
        entry for the new-layer restriction (``_enumerate``). ``child_signatures`` is the composed-
        signature fast path's cache (``signature.compute_signature``) — value candidates only; a
        function candidate's signature is argument-sampled, a different computation (``compute_
        function_signature``), untouched by the fast path.
        """
        functions: list[tuple[Program, ArrowType]] = []
        for program, vtype in candidates:
            if isinstance(vtype, ArrowType):
                functions.append((program, vtype))
            else:
                signature = compute_signature(program, contexts, state.library, child_signatures)
                self._absorb_one(program, vtype, vtype, signature, pool, state, generation)
        if functions:
            arg_samples = self._argument_samples(functions, contexts, pool, state)
            for program, arrow in functions:
                signature = compute_function_signature(
                    program, arrow, contexts, arg_samples, state.library
                )
                _, result_type = peel_arrow(arrow)
                self._absorb_one(program, arrow, result_type, signature, pool, state, generation)

    def _absorb_one(
        self,
        program: Program,
        vtype: Type,
        output_type: Type,
        signature: Signature | None,
        pool: Pool,
        state: _RunState,
        generation: int,
    ) -> None:
        """Prune (fully-undefined or a *concrete* output-type mismatch) and dedup one candidate.

        ``output_type`` is what the signature's values inhabit — ``vtype`` for a value program, the
        function's ultimate result for a function value. A *polymorphic* output type is not pruned (its
        free vars match any value); the pool keys on ``vtype``.

        Every candidate's capability keys (primitive names / node kinds, ``search/tracking.py``)
        are computed once, here, and cached on the ``PoolEntry`` if pooled — its ultimate outcome
        (displaced / evicted / goal-unmatched / constraint-rejected / accepted) is resolved later,
        without re-walking the tree. ``generation`` (the composition round) is likewise cached on the
        pooled entry, driving the new-layer restriction (``_enumerate``).
        """
        index = state.tracker.considered
        state.tracker.considered += 1
        primitives = primitive_keys(program)
        if signature is None:
            state.tracker.record(index, program, primitives, Outcome.ERRORED)
            return
        if not free_type_vars(output_type) and not signature_matches_type(signature, output_type):
            state.tracker.record(index, program, primitives, Outcome.PRUNED)
            return
        cost = state.cost.of(program, state.train_examples, state.library)
        outcome = pool.add_dedup(vtype, signature, program, cost, primitives, index, generation)
        if not outcome.inserted:
            state.tracker.record(index, program, primitives, Outcome.DEDUPED)
            return
        if outcome.displaced is not None:
            displaced = outcome.displaced
            state.tracker.record(
                displaced.candidate_index,
                displaced.program,
                displaced.primitives,
                Outcome.DISPLACED,
            )

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
                    program.evaluate(
                        reference.input_grid, state.library, scope=reference.scope_binding
                    )
                )
            except Exception:  # a program that errors at the reference context yields no sample
                continue
            if len(values) >= size:
                break
        return values

    def _select_frontier(self, pool: Pool, budget: Budget, state: _RunState) -> Pool:
        """Keep the cheapest ``budget.max_pool`` entries to carry into the next round (§5.7),
        recording ``EVICTED`` for whatever gets dropped to make room."""
        kept, dropped = pool.cheapest(budget.max_pool)
        for entry in dropped:
            state.tracker.record(
                entry.candidate_index, entry.program, entry.primitives, Outcome.EVICTED
            )
        return kept


@dataclass(frozen=True, slots=True, kw_only=True)
class BeamBottomUpSearchEngine(BottomUpSearchEngine):
    """Bottom-up enumeration with a fixed beam: keep only the cheapest ``beam_width`` per round."""

    beam_width: int

    def _select_frontier(self, pool: Pool, budget: Budget, state: _RunState) -> Pool:
        kept, dropped = pool.cheapest(self.beam_width)
        for entry in dropped:
            state.tracker.record(
                entry.candidate_index, entry.program, entry.primitives, Outcome.EVICTED
            )
        return kept
