"""``forecast_cost``: a calibrated per-round PREDICTION of a search's cost — no execution.

Sibling of :mod:`estimate_cost`, and deliberately a different object. ``estimate_cost`` returns a
worst-case **ceiling** (it must never under-count, so it takes the full cartesian product of an
untyped pool); this returns a **forecast** (it should be close, so it may err either way). Use the
ceiling to prove a cell is affordable; use the forecast to plan one.

The model mirrors what the engine actually does, in three corrections over the ceiling:

1. **Typed census.** The pool is bucketed by type, and a primitive's slot draws only from its own
   type's bucket — so ``set_cell(Grid, Int, Int, Color)`` costs ``|grid| x |int| x |int| x |color|``
   (al14: 10,615 x 17 x 17 x 14 = 43M), not ``pool ** 4`` (1.6e13). This one correction is worth
   five orders of magnitude on the cell floors, and it is what makes the per-factor attribution
   below possible at all.
2. **The new-layer restriction.** The engine only composes tuples using at least one argument from
   the previous round (``search_engine.py::_uses_new_layer``), so round ``d``'s count is
   ``PROD(census_d) - PROD(census_{d-1})`` per primitive — ``estimate_cost``'s named "deliberate,
   unbuilt refinement", built here.
3. **Survival.** Next round's pool is not everything considered: it is what neither errored, nor
   was pruned, nor deduped away. The surviving fraction is measured, not assumed — pass a short
   run's own funnel to :func:`survival_from` and the forecast is calibrated to that cell.

What stays approximate, and is flagged rather than hidden: ``max_pool`` truncation is modelled as a
proportional shrink across types, where the engine cuts cheapest-first (which biases toward the
types whose entries are cheap); a polymorphic slot is modelled as drawing from the whole pool; and
lambda synthesis is not modelled at all (same gap ``estimate_cost`` flags).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from math import prod

from arc_lab.core.task import Task, train_with_output
from arc_lab.program_search.search.context import Context
from arc_lab.program_search.search.leaves import seed_leaves
from arc_lab.program_search.search.scope import Scope
from arc_lab.program_search.search.search_engine import (
    BRANCHING_ENTRY,
    BeamBottomUpSearchEngine,
    BottomUpSearchEngine,
)
from arc_lab.program_search.search.search_result import SearchStats
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.types import Type, TypeVar

from .model.config import Config

#: Fraction of composed candidates that reach the pool when nothing better is known — the median
#: ``entered_pool / composed`` MEASURED across the ladder batch's rung cells (0.445 over 265
#: rounds; 2026-07-22 backtest, `experiments/2026-07-22-rung-probe/artifacts/forecast_backtest.py`).
#: A crude prior on purpose: pass a measured profile via :func:`survival_from` whenever a short run
#: of the same cell is available, which is the mode the rung probe uses.
DEFAULT_SURVIVAL = 0.44


@dataclass(frozen=True, slots=True)
class RoundForecast:
    """One composition round: the pool it composed over, and what it is predicted to build."""

    round_index: int
    #: Pooled entries per type name entering this round — the multiplicands of every product below.
    census: Mapping[str, int]
    composed: int
    entered_pool: int
    #: The primitive contributing the most candidates this round, and why: its slot census as a
    #: product string (``"set_cell: grid(10615) x int(17) x int(17) x color(14)"``). The answer to
    #: "which factor is eating the budget", read straight off the model.
    dominant: str = ""


@dataclass(frozen=True, slots=True)
class TaskForecast:
    """One task's predicted per-round cost and total."""

    task_id: str
    rounds: tuple[RoundForecast, ...]
    total_considered: int
    flags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def dominant_round(self) -> RoundForecast | None:
        """The round predicted to dominate the total — where the cost actually lives."""
        return max(self.rounds, key=lambda r: r.composed) if self.rounds else None


def survival_from(stats: SearchStats) -> tuple[float, ...]:
    """Per-round ``entered_pool / composed`` read off a real funnel — the calibration input.

    Rounds the search never reached contribute nothing; the forecaster carries the last observed
    rate forward, which is why probing two cheap rounds calibrates a projection of deeper ones.
    """
    rates: list[float] = []
    for generation in stats.generations:
        composed = generation.get("composed")
        entered = generation.get("entered_pool")
        if isinstance(composed, int) and isinstance(entered, int) and composed > 0:
            rates.append(entered / composed)
    return tuple(rates)


def forecast_cost(
    config: Config,
    task: Task,
    *,
    survival: float | Sequence[float] = DEFAULT_SURVIVAL,
    depth_limit: int | None = None,
) -> TaskForecast:
    """Predict ``considered`` per round for ``task`` under ``config``.

    ``survival`` is either one fraction for every round or a per-round sequence (from
    :func:`survival_from`), whose last entry is carried forward past the rounds it covers.
    ``depth_limit`` overrides the budget's, for projecting a deeper run than was ever executed.
    """
    engine = config.search_engine
    if not isinstance(engine, BottomUpSearchEngine):
        raise NotImplementedError(
            "cost forecasting is only implemented for BottomUpSearchEngine (and subclasses), "
            f"got {type(engine).__name__}"
        )
    budget = config.budget
    library = config.library
    horizon = budget.depth_limit if depth_limit is None else depth_limit
    cap = engine.beam_width if isinstance(engine, BeamBottomUpSearchEngine) else budget.max_pool
    flags: list[str] = list(_flags(config, engine))

    contexts = tuple(Context(example.input) for example in train_with_output(task.train))
    census: dict[Type, int] = {}
    for _, leaf_type in seed_leaves(Scope(()), contexts, engine.constant_sources, library):
        census[leaf_type] = census.get(leaf_type, 0) + 1
    leaf_total = sum(census.values())

    rounds = [
        RoundForecast(
            round_index=0,
            census={},
            composed=leaf_total,
            entered_pool=min(leaf_total, cap),
            dominant="round-0 leaves (exact: the engine's own seed_leaves)",
        )
    ]
    census = _capped(census, cap)
    previous: dict[Type, int] = {}

    for depth in range(1, horizon + 1):
        terms = _round_terms(library, census, previous, budget.max_arity)
        composed = sum(count for _, count in terms)
        if BRANCHING_ENTRY in library:
            composed += _branch_term(census, previous)
        rate = _rate(survival, depth)
        entered = round(composed * rate)
        rounds.append(
            RoundForecast(
                round_index=depth,
                census={_type_name(t): n for t, n in sorted(census.items(), key=_by_name)},
                composed=composed,
                entered_pool=entered,
                dominant=_attribute(terms, census),
            )
        )
        previous = dict(census)
        census = _capped(_grown(census, terms, rate), cap)

    return TaskForecast(
        task_id=task.task_id,
        rounds=tuple(rounds),
        total_considered=sum(r.composed for r in rounds),
        flags=tuple(flags),
    )


def _round_terms(
    library: Library,
    census: Mapping[Type, int],
    previous: Mapping[Type, int],
    max_arity: int,
) -> list[tuple[Primitive, int]]:
    """Per primitive, how many NEW tuples this round composes: PROD(now) - PROD(before)."""
    terms: list[tuple[Primitive, int]] = []
    for primitive in library.primitives:
        if primitive.name == BRANCHING_ENTRY:
            continue  # summons the If node; never applied as an ordinary primitive
        slot_sets = _slot_types(primitive, max_arity)
        count = 0
        for slots in slot_sets:
            now = prod(_available(t, census) for t in slots)
            before = prod(_available(t, previous) for t in slots)
            count += max(now - before, 0)
        terms.append((primitive, count))
    return terms


def _slot_types(primitive: Primitive, max_arity: int) -> list[tuple[Type, ...]]:
    """The argument-type tuples a primitive composes over — one per variadic arity."""
    if not primitive.is_variadic:
        return [primitive.param_types]
    fixed = primitive.param_types
    variadic = fixed[-1] if fixed else None
    if variadic is None:
        return [()]
    return [(*fixed, *([variadic] * extra)) for extra in range(max_arity)]


def _available(slot: Type, census: Mapping[Type, int]) -> int:
    """Pooled entries a slot can draw from — its own type, or the whole pool if polymorphic."""
    if isinstance(slot, TypeVar):
        return sum(census.values())
    return census.get(slot, 0)


def _branch_term(census: Mapping[Type, int], previous: Mapping[Type, int]) -> int:
    """``If`` candidates: a BOOL condition x ordered same-typed branch pairs, new-layer restricted."""

    def total(pool: Mapping[Type, int]) -> int:
        conditions = sum(n for t, n in pool.items() if _type_name(t) == "bool")
        pairs = sum(n * (n - 1) for t, n in pool.items() if _type_name(t) != "bool")
        return conditions * pairs

    return max(total(census) - total(previous), 0)


def _grown(
    census: Mapping[Type, int],
    terms: Sequence[tuple[Primitive, int]],
    rate: float,
) -> dict[Type, int]:
    """Next round's census: survivors added to their primitive's return-type bucket."""
    grown = dict(census)
    for primitive, count in terms:
        if count <= 0:
            continue
        bucket = primitive.return_type
        if isinstance(bucket, TypeVar):
            bucket = max(census, key=lambda t: census[t], default=bucket)  # polymorphic: flagged
        # At least one survivor per composing primitive: truncating to zero would freeze the
        # census, and a frozen census makes the NEXT round's new-layer term exactly zero -- the
        # forecast would collapse to 0 for every deeper round (seen on al3/al11 in the backtest).
        grown[bucket] = grown.get(bucket, 0) + max(round(count * rate), 1)
    return grown


def _capped(census: Mapping[Type, int], cap: int) -> dict[Type, int]:
    """Apply ``max_pool`` as a proportional shrink (the engine cuts cheapest-first — approximate)."""
    total = sum(census.values())
    if total <= cap or total == 0:
        return dict(census)
    scale = cap / total
    return {t: max(int(n * scale), 1) for t, n in census.items()}


def _rate(survival: float | Sequence[float], depth: int) -> float:
    """The survival fraction for this round: a constant, or the profile's entry (last carried on)."""
    if isinstance(survival, int | float):
        return float(survival)
    if not survival:
        return DEFAULT_SURVIVAL
    return float(survival[depth] if depth < len(survival) else survival[-1])


def _attribute(terms: Sequence[tuple[Primitive, int]], census: Mapping[Type, int]) -> str:
    """The round's dominant primitive as a readable product — the "which factor" answer."""
    if not terms:
        return ""
    primitive, count = max(terms, key=lambda item: item[1])
    if count <= 0:
        return ""
    slots = " x ".join(
        f"{_type_name(t)}({_available(t, census)})" for t in primitive.param_types
    )
    return f"{primitive.name}: {slots or 'nullary'}"


def _flags(config: Config, engine: BottomUpSearchEngine) -> tuple[str, ...]:
    flags: list[str] = []
    if any(isinstance(t, TypeVar) for p in config.library.primitives for t in p.param_types):
        flags.append(
            "a polymorphic primitive is present: its slots are modelled as drawing from the whole "
            "pool, which over-counts under 'monomorphize'."
        )
    if engine.function_hole_fill_mode == "lambda-synthesis":
        flags.append(
            "function_hole_fill_mode == 'lambda-synthesis': nested body searches are NOT modelled "
            "— this forecast is a lower bound."
        )
    elif engine.function_hole_fill_mode != "none":
        flags.append(
            "function_hole_fill_mode != 'none': pooled function values / AppFn are not modelled."
        )
    if config.learn is not None:
        flags.append(
            "LEARN config: this forecasts wake iteration 0 only — later wakes search a grown "
            "library."
        )
    return tuple(flags)


def _type_name(value: Type) -> str:
    return getattr(value, "name", str(value))


def _by_name(item: tuple[Type, int]) -> str:
    return _type_name(item[0])
