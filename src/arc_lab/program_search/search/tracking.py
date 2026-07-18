"""Capability tracking: the outcome partition and per-primitive breakdown of a search run, plus
opt-in sampling and full capture of the programs behind those counts.

Every candidate the engine considers terminates in exactly one :class:`Outcome` — the partition
invariant a :class:`SearchTracker` upholds is ``considered == sum(totals().values())``. Three
outcomes are known immediately when a candidate is absorbed (``ERRORED``, ``PRUNED``,
``DEDUPED``); the rest are resolved later, at the moment a pooled candidate's fate is finally
decided (``DISPLACED`` at a cheaper same-behaviour insertion, ``EVICTED`` at frontier truncation,
and ``GOAL_UNMATCHED``/``CONSTRAINT_REJECTED``/``ACCEPTED`` at pool finalization) — the
``PoolEntry`` is the identity that carries a candidate's cached ``primitives`` and
``candidate_index`` across that gap, so no separate per-program identity tracking is needed.

Each candidate has a ``candidate_index`` — a 0-based counter stamped when it is first considered
(``_absorb_one``). The tracker *invokes* a capture sink in *outcome-resolution* order, not
generation order (the terminal outcomes are recorded in a batch at the end), so the index is what
lets a consumer recover true consideration order — e.g. ``execute()``'s capture sink buffers on it
and writes the first ``max_count`` candidates back in generation order.

Counting is always on (cheap: a handful of dict increments per candidate, riding along with the
signature evaluation/cost computation ``_absorb_one`` already pays). Sampling (``samples``) and
full capture (``capture``) are opt-in, configured by whoever constructs the tracker
(``execution/execute.py``, from a ``TraceSpec``) — the engine itself never touches a file; a
capture sink is a plain callable, so this module has no I/O dependency at all.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, TypeAlias

from ..substrate.program import AppFn, Apply, Const, If, Lam, PrimRef, Program


class Outcome(Enum):
    """The eight mutually-exclusive terminal states of a considered candidate, in *funnel* order
    (the order they are emitted in every serialized stats block).

    - ERRORED: The candidate's evaluation raised an exception.
    - PRUNED: The candidate's signature doesn't match its type.
    - DEDUPED: The candidate's signature matches a previously-considered candidate's, and is more expensive.
    - DISPLACED: The candidate made it into the pool, but was later displaced by a cheaper same-behaviour candidate.
    - EVICTED: The candidate made it into the pool, but was later evicted by frontier truncation.
    - GOAL_UNMATCHED: The candidate made it to `extract`, but its output didn't match the goal.
    - CONSTRAINT_REJECTED: The candidate made it to `extract`, but failed one or more constraints.
    - ACCEPTED: The candidate made it to the end, and was returned as a potential solution by `SearchEngine.run`.
    """

    ERRORED = "errored"
    PRUNED = "pruned"
    DEDUPED = "deduped"
    DISPLACED = "displaced"
    EVICTED = "evicted"
    GOAL_UNMATCHED = "goal_unmatched"
    CONSTRAINT_REJECTED = "constraint_rejected"
    ACCEPTED = "accepted"


#: The funnel order — the canonical order every serialized stats block presents outcomes in.
OUTCOME_ORDER: tuple[Outcome, ...] = tuple(Outcome)
#: Outcome names in funnel order (the JSON keys).
OUTCOME_NAMES: tuple[str, ...] = tuple(outcome.value for outcome in OUTCOME_ORDER)
_OUTCOME_RANK: dict[str, int] = {name: index for index, name in enumerate(OUTCOME_NAMES)}


#: Node kinds that aren't a named primitive but are still a distinct search capability —
#: pseudo-keys alongside primitive names in the per-primitive breakdown.
_NODE_KIND_KEYS: dict[type[Program], str] = {
    If: "__if__",
    Lam: "__lam__",
    AppFn: "__appfn__",
    Const: "__const__",
}


def primitive_keys(program: Program) -> frozenset[str]:
    """The primitive names and node-kind pseudo-keys exercised anywhere in ``program``'s tree."""
    keys: set[str] = set()
    for node in program.walk():
        if isinstance(node, Apply):
            keys.add(node.primitive)
        elif isinstance(node, PrimRef):
            keys.add(node.name)
        else:
            key = _NODE_KIND_KEYS.get(type(node))
            if key is not None:
                keys.add(key)
    return frozenset(keys)


def funnel_outcomes(counts: dict[str, int], *, include_zeros: bool) -> dict[str, int]:
    """Re-emit an outcome-count dict in funnel order. ``include_zeros`` fills every outcome (a
    stable, self-documenting schema — for a ``total`` block); otherwise only the present ones
    (sparse — for a per-primitive row that would otherwise carry mostly zeros)."""
    if include_zeros:
        return {name: counts.get(name, 0) for name in OUTCOME_NAMES}
    return {name: counts[name] for name in OUTCOME_NAMES if name in counts}


SampleMode: TypeAlias = Literal["first_k", "cheapest_k"]


@dataclass(frozen=True, slots=True)
class SampleSpec:
    """One reservoir: keep up to ``k`` programs per ``(primitive, outcome)`` bucket.

    ``first_k`` keeps the first ``k`` encountered per bucket (arrival order, itself
    deterministic — no RNG anywhere in this codebase, so a sample must never depend on one).
    ``cheapest_k`` keeps the ``k`` smallest by ``program.size()`` — a structural property of
    the ``Program`` object alone, so this needs no ``Cost``/library plumbed into the tracker.
    """

    k: int
    mode: SampleMode


#: A capture sink is a plain callable — the tracker (and thus the search engine) never touches
#: a file; whoever configures the tracker (``execute()``) owns whatever the callable does.
CaptureSink: TypeAlias = Callable[[int, Program, frozenset[str], Outcome], None]

#: One sampled/captured program: its consideration index and the program itself.
_Sample: TypeAlias = "tuple[int, Program]"


def _offer(
    reservoir: dict[tuple[str, str], list[_Sample]],
    spec: SampleSpec,
    primitive: str,
    outcome: Outcome,
    candidate_index: int,
    program: Program,
) -> None:
    bucket = reservoir.setdefault((primitive, outcome.value), [])
    if spec.mode == "first_k":
        if len(bucket) < spec.k:
            bucket.append((candidate_index, program))
        return
    if len(bucket) < spec.k or program.size() < bucket[-1][1].size():
        bucket.append((candidate_index, program))
        bucket.sort(key=lambda entry: entry[1].size())
        del bucket[spec.k :]  # noqa: E203, RUF100


#: The composition round's own outcome-partition fields that ``record(generation=...)`` also
#: bumps on the matching ``GenerationTracker`` — ``goal_unmatched``/``constraint_rejected``/
#: ``accepted`` are excluded: those are only ever recorded once, at whole-run extraction, after
#: every round has already finished, so there is no live "current round" to attribute them to.
_GENERATION_OUTCOME_FIELDS: dict[Outcome, str] = {
    Outcome.ERRORED: "errored",
    Outcome.PRUNED: "pruned",
    Outcome.DEDUPED: "deduped",
    Outcome.DISPLACED: "displaced",
}


@dataclass(slots=True)
class GenerationTracker:
    """One composition round's live summary: pool size before/after, and where every candidate
    newly absorbed that round ended up. Deliberately ``Outcome``-free — unlike ``SearchTracker``'s
    own ``_totals``/``_by_primitive``, this never feeds sampling or capture (those bucket
    individual candidates across the *whole* run, not per-round aggregates), so there's no
    structural reason for it to speak ``Outcome`` at all.

    Only tracked for a run's one top-level search, never for a lambda-synthesis sub-search's own
    (much smaller, budget-descended) round loop — see ``SearchTracker.begin_generation``.
    """

    pool_size_start: int = 0
    pool_size_before_truncation: int | None = None
    pool_size_end: int | None = None
    #: New candidates absorbed this round: composed applications, ``If``-branch candidates, and
    #: (at generation 0) the leaf/seed layer — all absorbed through the same ``_absorb_one``
    #: choke point. Invariant: ``composed == errored + pruned + deduped + entered_pool``, mirroring
    #: ``SearchTracker``'s own ``considered == sum(totals().values())``.
    composed: int = 0
    errored: int = 0
    pruned: int = 0
    deduped: int = 0
    entered_pool: int = 0
    #: Entries (of any origin generation) displaced by *this* round's absorption.
    displaced: int = 0
    #: Entries (of any origin generation) evicted by *this* round's frontier truncation.
    evicted: int = 0


#: Default cap on solutions retained per run (keep-cheapest-K); solutions are rare, so this rarely
#: binds. Loud ``truncated`` when it does — only the count/all-solutions views degrade, never the
#: cheapest or first (those are O(1) running quantities, kept exact regardless of the cap).
DEFAULT_SOLUTION_CAP = 32


@dataclass(frozen=True, slots=True)
class SolutionRecord:
    """One goal-matching candidate observed at absorption, before the pool's ``(type, signature)``
    dedup collapses every solution into a single slot: its provenance and the program itself."""

    candidate_index: int
    generation: int
    cost: float
    program: Program


@dataclass(slots=True)
class SolutionSink:
    """Every candidate whose ``(type, signature) == (goal_type, target)``, captured at absorption
    (the engine tests this and calls :meth:`record`). The pool retains at most ONE solution entry
    ever (they all compete for the same slot), so the sink is the only place that sees the first-
    found and all-solutions before dedup — the atom behind cost-to-first / cost-to-cheapest and
    RQ3's top-K retention. Keeps the cheapest ``cap`` by ``(cost, candidate_index)`` — the SAME
    key the pool's strictly-cheaper-wins dedup uses (cheapest, then first-arrived), so the sink's
    cheapest reproduces the pool's retained identity exactly."""

    cap: int = DEFAULT_SOLUTION_CAP
    count: int = 0
    #: Min ``candidate_index`` over ALL goal-matches (kept exact even when the cap truncates).
    first_index: int | None = None
    truncated: bool = False
    _cheapest: list[SolutionRecord] = field(default_factory=list)

    def record(self, candidate_index: int, generation: int, program: Program, cost: float) -> None:
        self.count += 1
        if self.first_index is None or candidate_index < self.first_index:
            self.first_index = candidate_index
        self._cheapest.append(SolutionRecord(candidate_index, generation, cost, program))
        self._cheapest.sort(key=lambda record: (record.cost, record.candidate_index))
        if len(self._cheapest) > self.cap:
            del self._cheapest[self.cap :]  # noqa: E203, RUF100
            self.truncated = True

    def cheapest(self) -> SolutionRecord | None:
        """The globally-cheapest solution (min ``(cost, candidate_index)``), or ``None``."""
        return self._cheapest[0] if self._cheapest else None

    def records(self) -> tuple[SolutionRecord, ...]:
        """The retained cheapest-``cap`` solutions, cheapest first."""
        return tuple(self._cheapest)


@dataclass(slots=True)
class SearchTracker:
    """Accumulates the outcome partition + per-primitive breakdown for one ``SearchEngine.run``
    call, plus whatever sampling/capture it was configured with."""

    considered: int = 0
    #: The task this tracker was constructed for (``execute()``'s ``_make_tracker``) — pure
    #: metadata for logging (never influences search behavior), so it doesn't touch the
    #: train/test blindness seam.
    task_id: str | None = None
    #: Reservoir samplers to maintain — () means no sampling (the cheapest option).
    samples: tuple[SampleSpec, ...] = ()
    #: Set by ``execute()`` when full capture is requested; ``None`` means never called.
    capture: CaptureSink | None = None
    #: Keep-cheapest-K cap for the solution sink (from the run's ``TraceSpec``).
    solution_cap: int = DEFAULT_SOLUTION_CAP
    _totals: dict[Outcome, int] = field(default_factory=dict)
    _by_primitive: dict[str, dict[Outcome, int]] = field(default_factory=dict)
    _reservoirs: dict[SampleSpec, dict[tuple[str, str], list[_Sample]]] = field(
        default_factory=dict
    )
    #: One entry per round of the run's top-level search (never a lambda-synthesis sub-search's
    #: own round loop — ``begin_generation``'s docstring). A list, not a dict keyed by round
    #: number, since rounds run ``0..max_depth-1`` contiguously.
    _generations: list[GenerationTracker] = field(default_factory=list)
    #: Every goal-matching candidate the top-level search absorbed (``record_solution``). The engine
    #: draws its returned result from here (the globally-cheapest, evicted or not); the outcome
    #: partition stays pool-based, so the two can legitimately disagree on an eviction-loss task.
    solutions: SolutionSink = field(init=False)

    def __post_init__(self) -> None:
        self.solutions = SolutionSink(cap=self.solution_cap)

    def record_solution(
        self, candidate_index: int, generation: int, program: Program, cost: float
    ) -> None:
        """Record a candidate whose ``(type, signature)`` matched the run's goal (the engine tests
        this and calls here) — orthogonal to the outcome partition, so not a ``record()`` call."""
        self.solutions.record(candidate_index, generation, program, cost)

    def record(
        self,
        candidate_index: int,
        program: Program,
        primitives: frozenset[str],
        outcome: Outcome,
        *,
        generation: int | None = None,
    ) -> None:
        self._totals[outcome] = self._totals.get(outcome, 0) + 1
        for primitive in primitives:
            bucket = self._by_primitive.setdefault(primitive, {})
            bucket[outcome] = bucket.get(outcome, 0) + 1
        for spec in self.samples:
            reservoir = self._reservoirs.setdefault(spec, {})
            for primitive in primitives:
                _offer(reservoir, spec, primitive, outcome, candidate_index, program)
        if self.capture is not None:
            self.capture(candidate_index, program, primitives, outcome)
        if generation is not None:
            field_name = _GENERATION_OUTCOME_FIELDS.get(outcome)
            if field_name is not None:
                gen_tracker = self._generations[generation]
                setattr(gen_tracker, field_name, getattr(gen_tracker, field_name) + 1)
                if outcome is not Outcome.DISPLACED:  # displaced isn't part of `composed`
                    gen_tracker.composed += 1

    def begin_generation(self, pool_size_start: int) -> None:
        """Start tracking a new round of the run's *top-level* search — never call this for a
        lambda-synthesis sub-search's own round loop (``BottomUpSearchEngine._enumerate``'s
        ``top_level=False`` calls): those recurse with the same shared tracker but their own
        ``depth`` numbering starting again at 0, which would otherwise collide with (and
        silently corrupt) the top-level search's own generation 0, 1, 2, ... entries."""
        self._generations.append(GenerationTracker(pool_size_start=pool_size_start))

    def mark_entered_pool(self, generation: int | None) -> None:
        """A candidate was freshly pooled (survived absorption, terminal fate still open) —
        not a ``record()`` call since ``entered_pool`` isn't a terminal ``Outcome``. A no-op
        when ``generation`` is ``None`` (a lambda-synthesis sub-search's own absorption —
        mirrors ``record()``'s own ``generation=None`` no-op)."""
        if generation is None:
            return
        gen_tracker = self._generations[generation]
        gen_tracker.entered_pool += 1
        gen_tracker.composed += 1

    def mark_pool_size_before_truncation(self, generation: int, pool_size: int) -> None:
        self._generations[generation].pool_size_before_truncation = pool_size

    def end_generation(self, generation: int, pool_size_end: int) -> None:
        self._generations[generation].pool_size_end = pool_size_end

    def generation_at(self, generation: int) -> GenerationTracker:
        return self._generations[generation]

    def generations(self) -> list[dict[str, int | None]]:
        """The per-round funnel as serializable rows in round order — the sole source for ``b_eff``
        fitting and the vocabulary-tax view. Top-level search only (a lambda-synthesis sub-search
        never calls ``begin_generation``), so this is empty for those."""
        return [
            {
                "pool_size_start": gen.pool_size_start,
                "pool_size_before_truncation": gen.pool_size_before_truncation,
                "pool_size_end": gen.pool_size_end,
                "composed": gen.composed,
                "errored": gen.errored,
                "pruned": gen.pruned,
                "deduped": gen.deduped,
                "entered_pool": gen.entered_pool,
                "displaced": gen.displaced,
                "evicted": gen.evicted,
            }
            for gen in self._generations
        ]

    def totals(self) -> dict[str, int]:
        """Outcome totals by name, funnel order, all outcomes present (zeros filled) — the stable
        schema for a ``total`` block. ``considered == sum(totals().values())``."""
        return funnel_outcomes(
            {outcome.value: count for outcome, count in self._totals.items()}, include_zeros=True
        )

    def by_primitive(self) -> dict[str, dict[str, int]]:
        """Outcome totals per primitive-name / node-kind key: primitives sorted, outcomes in
        funnel order, zeros omitted (a per-primitive row is sparse by design)."""
        return {
            primitive: funnel_outcomes(
                {outcome.value: count for outcome, count in self._by_primitive[primitive].items()},
                include_zeros=False,
            )
            for primitive in sorted(self._by_primitive)
        }

    def sample_rows(self) -> list[dict[str, object]]:
        """The sampled programs as flat rows ``{candidate_index, primitive, outcome, program}``
        (``program`` a readable string), one per ``(primitive, outcome, candidate_index)``,
        deduplicated across configured samplers and sorted by primitive, then funnel order, then
        index — so buckets group visually and the SAME tooling renders this and a capture file."""
        seen: dict[tuple[str, str, int], Program] = {}
        for reservoir in self._reservoirs.values():
            for (primitive, outcome), entries in reservoir.items():
                for candidate_index, program in entries:
                    seen[(primitive, outcome, candidate_index)] = program
        rows: list[dict[str, object]] = []
        for primitive, outcome, candidate_index in sorted(
            seen, key=lambda bucket: (bucket[0], _OUTCOME_RANK.get(bucket[1], 99), bucket[2])
        ):
            rows.append(
                {
                    "candidate_index": candidate_index,
                    "primitive": primitive,
                    "outcome": outcome,
                    "program": str(seen[(primitive, outcome, candidate_index)]),
                }
            )
        return rows
