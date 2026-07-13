"""Extraction: the goal test that reads solutions off a built pool (§5.8 of ARCHITECTURE.md).

``_enumerate`` builds the full pool with no goal or target; extraction is the separate, thin step run
against it. A program *solves* the task iff it has the goal type and its signature equals ``target``
(the training outputs). Because ``target`` is a total signature and ``⊥ ≠ v``, ``sig == target``
already implies totality on the training contexts — no separate check. Consistency-with-training *is*
``sig == target``; ``constraints`` holds only the *extra* inductive-bias filters on the survivors.
"""

from __future__ import annotations

from dataclasses import dataclass

from arc_lab.core.task import TrainExamples

from ..substrate.library import Library
from ..substrate.types import Type
from .constraints import Constraint
from .pool import Pool, PoolEntry
from .signature import Signature


@dataclass(frozen=True, slots=True)
class Extraction:
    """The goal-matched entries of a finished pool, split by whether they pass every constraint.

    ``accepted`` is ranked (cheapest first, deterministic tiebreak) — the solutions a
    ``SearchEngine.run`` returns. ``constraint_rejected`` is unranked: it exists so a caller can
    attribute the ``CONSTRAINT_REJECTED`` outcome (capability tracking, ``search/tracking.py``),
    not for consumption as solutions.
    """

    accepted: tuple[PoolEntry, ...]
    constraint_rejected: tuple[PoolEntry, ...]


def extract(
    pool: Pool,
    goal_type: Type,
    target: Signature,
    constraints: tuple[Constraint, ...],
    train_examples: TrainExamples,
    library: Library,
) -> Extraction:
    """Split ``pool``'s goal-matched entries into constraint-passing and constraint-rejected.

    Ranked by an explicit key — cached cost, then program size, then serialization — so equal costs
    fall to a deterministic tiebreak and `Program`s are never compared directly (which would
    raise).

    Costs are read straight from the pooled entries (cached once at insertion, §5.7); nothing
    is re-evaluated here.
    """
    goal_matched = [entry for entry in pool.items_of_type(goal_type) if entry.sig == target]
    accepted: list[PoolEntry] = []
    rejected: list[PoolEntry] = []
    for entry in goal_matched:
        if all(
            constraint.holds(entry.program, train_examples, library) for constraint in constraints
        ):
            accepted.append(entry)
        else:
            rejected.append(entry)
    accepted.sort(key=lambda entry: (entry.cost, entry.program.size(), str(entry.program)))
    return Extraction(accepted=tuple(accepted), constraint_rejected=tuple(rejected))
