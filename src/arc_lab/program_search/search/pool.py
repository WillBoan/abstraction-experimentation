"""The pool: the observational-equivalence dedup store at the heart of bottom-up search.

Keyed ``type → signature → PoolEntry``, it holds exactly one program per ``(type, behaviour)`` — the
cheapest — so distinct syntax with the same behaviour collapses to a single representative (§5.7 of
ARCHITECTURE.md). Cost is cached on the entry at insertion, so dedup tie-breaks, frontier truncation,
ranking, and extraction all read a number rather than re-evaluating.

The pool is mutable engine scratch: never hashed, never part of the run identity.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from ..substrate.program import Program
from ..substrate.types import Type
from .signature import Signature


@dataclass(frozen=True, slots=True)
class PoolEntry:
    """One pooled behaviour: the cheapest program of a ``(type, signature)``, with its cached cost."""

    program: Program
    sig: Signature
    cost: float
    #: Primitive names / node-kind pseudo-keys exercised in ``program``'s tree (capability
    #: tracking, ``search/tracking.py``) — cached at insertion so a deferred outcome (displaced,
    #: evicted, goal-unmatched, ...) can be attributed without re-walking the tree.
    primitives: frozenset[str] = frozenset()
    #: The candidate's 0-based consideration index (``SearchTracker`` — stamped at ``_absorb_one``),
    #: cached so a deferred outcome recovers the program's true generation order.
    candidate_index: int = 0


@dataclass(frozen=True, slots=True)
class DedupOutcome:
    """The result of one ``add_dedup`` call: whether the candidate was inserted, and — if it
    replaced a costlier same-behaviour witness — that displaced entry (for attribution)."""

    inserted: bool
    displaced: PoolEntry | None


@dataclass(slots=True)
class Pool:
    """The ``type → signature → PoolEntry`` observational-equivalence dedup store."""

    _by_type_sig: dict[Type, dict[Signature, PoolEntry]] = field(default_factory=dict)

    def add_dedup(
        self,
        vtype: Type,
        signature: Signature,
        program: Program,
        cost: float,
        primitives: frozenset[str] = frozenset(),
        candidate_index: int = 0,
    ) -> DedupOutcome:
        """Insert ``program`` iff it is the first — or strictly cheaper — witness at ``(vtype, signature)``.

        Returns a :class:`DedupOutcome`: ``inserted=False`` if an existing entry was at most as
        costly, so ``program`` is deduplicated away; ``inserted=True`` otherwise, carrying the
        displaced entry (if any) so its capability tags can be attributed to ``DISPLACED``.
        """
        sig_map = self._by_type_sig.setdefault(vtype, {})
        existing = sig_map.get(signature)
        if existing is None or cost < existing.cost:
            sig_map[signature] = PoolEntry(program, signature, cost, primitives, candidate_index)
            return DedupOutcome(inserted=True, displaced=existing)
        return DedupOutcome(inserted=False, displaced=None)

    def types(self) -> tuple[Type, ...]:
        """The distinct types currently pooled, in first-insertion order (deterministic)."""
        return tuple(self._by_type_sig)

    def of_type(self, vtype: Type) -> Iterable[Program]:
        """The programs of type ``vtype`` — feeds composition (§5.2)."""
        return (entry.program for entry in self._by_type_sig.get(vtype, {}).values())

    def items_of_type(self, vtype: Type) -> Iterable[PoolEntry]:
        """The entries of type ``vtype``, carrying signature + cached cost for the goal test (§5.8)."""
        return iter(self._by_type_sig.get(vtype, {}).values())

    def typed_programs(self) -> Iterable[tuple[Program, Type]]:
        """Every pooled program paired with its type — the argument candidates for composition (§5.2).

        Not bucketed by type: composition decides argument compatibility by *unification* (a
        polymorphic parameter accepts any type), so it needs the flat typed stream.
        """
        return ((entry.program, vtype) for vtype, entry in self.entries())

    def cheapest(self, n: int) -> tuple[Pool, tuple[PoolEntry, ...]]:
        """The globally-cheapest ``n`` entries as a new pool, re-bucketed by type, plus the
        entries dropped to get there (for ``EVICTED`` attribution).

        A frontier-truncation *primitive*: the policy (how many, type-awareness) lives in the
        engine's ``_select_frontier``. Ties break by insertion order, keeping the cut deterministic.
        """
        ordered = sorted(self.entries(), key=lambda item: item[1].cost)
        kept: dict[Type, dict[Signature, PoolEntry]] = {}
        for vtype, entry in ordered[:n]:
            kept.setdefault(vtype, {})[entry.sig] = entry
        dropped = tuple(entry for _, entry in ordered[n:])
        return Pool(_by_type_sig=kept), dropped

    def ranked(self) -> tuple[Program, ...]:
        """Every program in the pool, cheapest first — a whole-pool view, **not** the solution set."""
        ordered = sorted(self.entries(), key=lambda item: item[1].cost)
        return tuple(entry.program for _, entry in ordered)

    def size(self) -> int:
        """The total number of programs held across all types."""
        return sum(len(sig_map) for sig_map in self._by_type_sig.values())

    def entries(self) -> Iterable[tuple[Type, PoolEntry]]:
        """Every ``(type, entry)`` pair — backs the type-aware whole-pool operations."""
        return (
            (vtype, entry)
            for vtype, sig_map in self._by_type_sig.items()
            for entry in sig_map.values()
        )
