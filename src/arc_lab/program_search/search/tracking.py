"""Capability tracking: the outcome partition and per-key (primitive/node-kind) breakdown of a
search run, plus opt-in sampling and full capture of the programs behind those counts.

Every candidate the engine considers terminates in exactly one :class:`Outcome` — the partition
invariant a :class:`SearchTracker` upholds is ``considered == sum(totals().values())``. Three
outcomes are known immediately when a candidate is absorbed (``ERRORED``, ``PRUNED``,
``DEDUPED``); the rest are resolved later, at the moment a pooled candidate's fate is finally
decided (``DISPLACED`` at a cheaper same-behaviour insertion, ``EVICTED`` at frontier truncation,
and ``GOAL_UNMATCHED``/``CONSTRAINT_REJECTED``/``ACCEPTED`` at pool finalization) — the
``PoolEntry`` is the identity that carries a candidate's cached ``prim_keys`` across that gap, so
no per-program identity tracking is needed.

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
    """The eight mutually-exclusive terminal states of a considered candidate."""

    ERRORED = "errored"
    PRUNED = "pruned"
    DEDUPED = "deduped"
    DISPLACED = "displaced"
    EVICTED = "evicted"
    GOAL_UNMATCHED = "goal_unmatched"
    CONSTRAINT_REJECTED = "constraint_rejected"
    ACCEPTED = "accepted"


#: Node kinds that aren't a named primitive but are still a distinct search capability —
#: pseudo-keys alongside primitive names in the per-key breakdown.
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


SampleMode: TypeAlias = Literal["first_k", "cheapest_k"]


@dataclass(frozen=True, slots=True)
class SampleSpec:
    """One reservoir: keep up to ``k`` programs per ``(key, outcome)`` bucket.

    ``first_k`` keeps the first ``k`` encountered per bucket (arrival order, itself
    deterministic — no RNG anywhere in this codebase, so a sample must never depend on one).
    ``cheapest_k`` keeps the ``k`` smallest by ``program.size()`` — a structural property of
    the ``Program`` object alone, so this needs no ``Cost``/library plumbed into the tracker.
    """

    k: int
    mode: SampleMode


#: A capture sink is a plain callable — the tracker (and thus the search engine) never touches
#: a file; whoever configures the tracker (``execute()``) owns whatever the callable does.
CaptureSink: TypeAlias = Callable[[Program, frozenset[str], Outcome], None]


def _offer(
    reservoir: dict[tuple[str, str], list[Program]],
    spec: SampleSpec,
    key: str,
    outcome: Outcome,
    program: Program,
) -> None:
    bucket = reservoir.setdefault((key, outcome.value), [])
    if spec.mode == "first_k":
        if len(bucket) < spec.k:
            bucket.append(program)
        return
    if len(bucket) < spec.k or program.size() < bucket[-1].size():
        bucket.append(program)
        bucket.sort(key=lambda candidate: candidate.size())
        del bucket[spec.k :]


@dataclass(slots=True)
class SearchTracker:
    """Accumulates the outcome partition + per-key breakdown for one ``SearchEngine.run`` call,
    plus whatever sampling/capture it was configured with."""

    considered: int = 0
    #: Reservoir samplers to maintain — () means no sampling (the cheapest option).
    samples: tuple[SampleSpec, ...] = ()
    #: Set by ``execute()`` when full capture is requested; ``None`` means never called.
    capture: CaptureSink | None = None
    _totals: dict[Outcome, int] = field(default_factory=dict)
    _by_key: dict[str, dict[Outcome, int]] = field(default_factory=dict)
    _reservoirs: dict[SampleSpec, dict[tuple[str, str], list[Program]]] = field(
        default_factory=dict
    )

    def record(self, program: Program, keys: frozenset[str], outcome: Outcome) -> None:
        self._totals[outcome] = self._totals.get(outcome, 0) + 1
        for key in keys:
            bucket = self._by_key.setdefault(key, {})
            bucket[outcome] = bucket.get(outcome, 0) + 1
        for spec in self.samples:
            reservoir = self._reservoirs.setdefault(spec, {})
            for key in keys:
                _offer(reservoir, spec, key, outcome, program)
        if self.capture is not None:
            self.capture(program, keys, outcome)

    def totals(self) -> dict[str, int]:
        """Outcome totals by name — ``considered == sum(totals().values())``."""
        return {outcome.value: count for outcome, count in self._totals.items()}

    def by_key(self) -> dict[str, dict[str, int]]:
        """Outcome totals by name, broken down per primitive-name / node-kind key."""
        return {
            key: {outcome.value: count for outcome, count in bucket.items()}
            for key, bucket in self._by_key.items()
        }

    def samples_json(self) -> dict[str, dict[str, list[dict[str, object]]]]:
        """Every configured reservoir's contents, JSON-ready: ``{"k{k}_{mode}": {"key|outcome":
        [program dicts, cheapest/first first]}}``."""
        return {
            f"k{spec.k}_{spec.mode}": {
                f"{key}|{outcome}": [program.to_dict() for program in programs]
                for (key, outcome), programs in reservoir.items()
            }
            for spec, reservoir in self._reservoirs.items()
        }
