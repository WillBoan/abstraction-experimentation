"""``estimate_cost``: a static worst-case search-cost ceiling for a ``RunSpec`` — no execution.

Reads ``RunSpec.config`` (machinery) and ``RunSpec.corpus`` (content) and returns, per task, a
round-by-round bound on ``SearchStats.considered`` (``search_engine.py``'s ``_Tally.considered`` —
every candidate the engine builds and evaluates, whether or not it survives pruning/dedup) without
ever calling ``SearchEngine.run``.

**What's modeled exactly:** round-0 leaves (via the real ``seed_leaves``, so no drift from the
engine's own leaf logic) and fixed/variadic primitive composition (``pool_size ** arity``, summed
over the library and, for a variadic primitive, over ``1..budget.max_arity``) — a genuine ceiling,
since ``_fill`` only ever *skips* combinations on a failed ``unify``; it never explores more than the
full cartesian product this counts. The per-round pool is capped exactly as ``_select_frontier``
caps it (``budget.max_pool``, or ``beam_width`` under ``BeamBottomUpSearchEngine``).

**What's a heuristic, not a ceiling:** short-circuit ``If`` branching and the function-hole
fill/``AppFn`` path (§5.3-5.4 of ARCHITECTURE.md) are dormant in every current preset
(``execution/presets.py``), so they are approximated rather than derived from the engine's exact
per-type permutation/currying logic — see ``_config_flags``. ``lambda-synthesis`` recurses into a
whole nested search per function-typed hole and is not modeled at all: when it is active, the
returned total is a *lower* bound, not a safe ceiling (flagged explicitly, per this repo's
convention of a visible gap over a silently wrong number — see ``derive_goal_type``).

A ``LEARN`` run's ``config.learn`` grows the library each wake via invention (SEARCH-SPACE.md:
"invention can re-introduce a capability you thought you removed by emptying the bag"), so this
estimate only ever bounds wake iteration 0 — flagged, not extrapolated across iterations.
"""

from __future__ import annotations

from dataclasses import dataclass

from arc_lab.core.task import Task, train_with_output
from arc_lab.program_search.search.context import Context
from arc_lab.program_search.search.leaves import seed_leaves
from arc_lab.program_search.search.scope import Scope
from arc_lab.program_search.search.search_engine import (
    BeamBottomUpSearchEngine,
    BottomUpSearchEngine,
)
from arc_lab.program_search.substrate.library import Library

from .model.config import Config
from .model.run_spec import RunSpec

#: The library's branching token — mirrors ``search_engine.py``'s ``_BRANCHING_ENTRY``: present as a
#: name, never applied as an ordinary primitive.
_BRANCHING_ENTRY = "if"


@dataclass(frozen=True, slots=True)
class RoundEstimate:
    """One composition round's bound: the pool size it composed over and candidates it built."""

    round_index: int
    incoming_pool: int
    considered: int


@dataclass(frozen=True, slots=True)
class TaskCostEstimate:
    """One task's per-round ceiling and total."""

    task_id: str
    rounds: tuple[RoundEstimate, ...]
    total_considered_ceiling: int


@dataclass(frozen=True, slots=True)
class CostEstimate:
    """A corpus-wide ceiling: one :class:`TaskCostEstimate` per task, plus config-level caveats."""

    tasks: tuple[TaskCostEstimate, ...]
    total_considered_ceiling: int
    flags: tuple[str, ...]

    @property
    def worst_task(self) -> TaskCostEstimate | None:
        """The task with the highest ceiling, or ``None`` for an empty corpus."""
        if not self.tasks:
            return None
        return max(self.tasks, key=lambda t: t.total_considered_ceiling)


def estimate_cost(run_spec: RunSpec) -> CostEstimate:
    """A worst-case ``considered`` ceiling per task in ``run_spec.corpus``, under ``run_spec.config``.

    Raises ``NotImplementedError`` for a ``search_engine`` that isn't a
    :class:`BottomUpSearchEngine` (or subclass) — there is no other engine to model yet.
    """
    config = run_spec.config
    if not isinstance(config.search_engine, BottomUpSearchEngine):
        raise NotImplementedError(
            "cost estimation is only implemented for BottomUpSearchEngine (and subclasses), "
            f"got {type(config.search_engine).__name__}"
        )
    tasks = tuple(_estimate_task(task, config) for task in run_spec.corpus)
    total = sum(task.total_considered_ceiling for task in tasks)
    return CostEstimate(tasks=tasks, total_considered_ceiling=total, flags=_config_flags(config))


def _estimate_task(task: Task, config: Config) -> TaskCostEstimate:
    engine = config.search_engine
    assert isinstance(engine, BottomUpSearchEngine)  # narrowed by estimate_cost's guard
    budget = config.budget
    library = config.library
    cap = engine.beam_width if isinstance(engine, BeamBottomUpSearchEngine) else budget.max_pool

    rounds: list[RoundEstimate] = []
    if budget.max_depth >= 1:
        leaf_count = _leaf_count(task, engine, library)
        rounds.append(RoundEstimate(round_index=0, incoming_pool=0, considered=leaf_count))
        pool = min(leaf_count, cap)
        for depth in range(1, budget.max_depth):
            considered = _compose_term(pool, library, budget.max_arity)
            if _BRANCHING_ENTRY in library:
                considered += _branch_term(pool)
            if engine.function_hole_fill_mode != "none":
                considered += _appfn_term(pool, library)
            rounds.append(
                RoundEstimate(round_index=depth, incoming_pool=pool, considered=considered)
            )
            pool = min(considered, cap)

    total = sum(round_.considered for round_ in rounds)
    return TaskCostEstimate(
        task_id=task.task_id, rounds=tuple(rounds), total_considered_ceiling=total
    )


def _leaf_count(task: Task, engine: BottomUpSearchEngine, library: Library) -> int:
    """Round-0 leaves: the real ``seed_leaves`` (no drift) plus function-value leaves if fillable."""
    train = train_with_output(task.train)
    contexts = tuple(Context(example.input) for example in train)
    leaves = sum(1 for _ in seed_leaves(Scope(()), contexts, engine.constant_sources))
    if engine.function_hole_fill_mode != "none":
        leaves += sum(1 for prim in library.primitives if prim.name != _BRANCHING_ENTRY)
    return leaves


def _compose_term(pool_size: int, library: Library, max_arity: int) -> int:
    """The exact composition ceiling: ``pool_size ** arity`` per primitive, summed over the library.

    A safe upper bound on ``applications()``/``_fill``'s output: every failed ``unify`` only ever
    *prunes* a branch of the cartesian product this counts, never adds to it.
    """
    total = 0
    for primitive in library.primitives:
        if primitive.name == _BRANCHING_ENTRY:
            continue
        if primitive.is_variadic:
            fixed_arity = len(primitive.param_types)
            for variadic_arity in range(1, max_arity + 1):
                total += pool_size ** (fixed_arity + variadic_arity)
        else:
            total += pool_size**primitive.arity
    return total


def _branch_term(pool_size: int) -> int:
    """Heuristic bound on ``_branch_candidates``: conditions x same-type (then, orelse) pairs.

    Not a derived ceiling (it doesn't bucket ``pool_size`` by type the way the real per-type
    ``itertools.permutations`` pass does) — flagged by ``_config_flags`` whenever it applies.
    """
    return pool_size**3


def _appfn_term(pool_size: int, library: Library) -> int:
    """Heuristic bound on ``appfn_applications`` + function-hole fill: pool x pool^(max primitive arity).

    No pooled function value's arrow can exceed the highest-arity primitive in the library, so this
    over-counts rather than under-counts — but it is not derived from the real currying/argument-fill
    logic, so it is flagged rather than trusted as an exact ceiling.
    """
    max_arity = max((p.arity for p in library.primitives if p.name != _BRANCHING_ENTRY), default=0)
    return int(pool_size ** (max_arity + 1))


def _config_flags(config: Config) -> tuple[str, ...]:
    """Caveats for whichever capabilities this estimate only approximates or can't bound at all."""
    engine = config.search_engine
    assert isinstance(engine, BottomUpSearchEngine)
    flags: list[str] = []
    if _BRANCHING_ENTRY in config.library:
        flags.append(
            "branching ('if') is active: the branch-candidate term is a heuristic "
            "(pool_size**3), not the engine's exact per-type permutation count."
        )
    if engine.function_hole_fill_mode != "none":
        flags.append(
            "function_hole_fill_mode != 'none': the function-leaf/AppFn terms are a heuristic "
            "bound (pool_size**(max primitive arity + 1)), not exact."
        )
    if engine.function_hole_fill_mode == "lambda-synthesis":
        flags.append(
            "function_hole_fill_mode == 'lambda-synthesis': recursive lambda-body search is NOT "
            "modeled at all — this total is a LOWER bound only, not a safe ceiling."
        )
    if engine.polymorphism_instantiation != "monomorphize":
        flags.append(
            f"polymorphism_instantiation == {engine.polymorphism_instantiation!r}: leaf/compose "
            "counts assume one candidate per typed program (monomorphize); 'bounded'/'unrestricted' "
            "can pool more per type, so this estimate may undercount."
        )
    if config.learn is not None:
        flags.append(
            "LEARN run (config.learn is set): this estimate bounds a single SEARCH pass only "
            "(wake iteration 0). Later wakes re-search with a library grown by sleep-invented "
            "primitives — not predicted here."
        )
    return tuple(flags)
