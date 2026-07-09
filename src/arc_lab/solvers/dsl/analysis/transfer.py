"""Transfer: read-side reducers over stored run summaries.

The analysis (read-side) tier — these consume already-computed :class:`RunSummary` objects and
derive the transfer signals, never running anything themselves. :func:`heldout_transfer` is the
*grade* (held-out only, never a governance signal); :func:`enablement_transfer` is its same-corpus
diagnostic; :func:`train_usefulness` is a train-side proxy governance may consume, kept separate so
the grade stays uncontaminated.
"""

from __future__ import annotations

from dataclasses import dataclass

from arc_lab.solvers.dsl.analysis.compression import speedup_ratio
from arc_lab.solvers.dsl.analysis.runner import RunSummary


def enablement_transfer(base: RunSummary, augmented: RunSummary) -> frozenset[str]:
    """Tasks the augmented library solves that the base one does not — enablement transfer."""
    return augmented.solved_ids - base.solved_ids


def _restrict(summary: RunSummary, ids: frozenset[str]) -> tuple[frozenset[str], int]:
    """``(solved ids, nodes considered)`` restricted to ``ids`` — a train-only or held-out slice."""
    solved = frozenset(r.task_id for r in summary.records if r.solved and r.task_id in ids)
    considered = sum(r.considered for r in summary.records if r.task_id in ids)
    return solved, considered


def heldout_transfer(
    base: RunSummary, augmented: RunSummary, heldout_ids: frozenset[str]
) -> frozenset[str]:
    """Held-out tasks the augmented library solves that the base does not — the transfer *grade*.

    The held-out counterpart to :func:`enablement_transfer` (which is same-corpus): this is the
    metric the disciplines *grade* with — never a governance signal. ``heldout_ids`` is the set of
    task ids the loop did **not** learn on.
    """
    return (augmented.solved_ids - base.solved_ids) & heldout_ids


@dataclass(frozen=True, slots=True)
class Usefulness:
    """A **train-side** proxy for a learned library's worth — safe for governance to consume, so
    the held-out grade stays uncontaminated.

    ``speedup`` is train nodes-considered ``base / augmented``; ``enabled`` is the train tasks the
    augmented library newly reaches at the (shallow) budget.
    """

    speedup: float
    enabled: frozenset[str]


def train_usefulness(
    deep_base: RunSummary,
    deep_augmented: RunSummary,
    shallow_base: RunSummary,
    shallow_augmented: RunSummary,
    train_ids: frozenset[str],
) -> Usefulness:
    """The train-side usefulness of a learned library — both facets restricted to train, so the
    held-out grade stays independent:

    * ``speedup`` — the *deep*-search effort reduction (the bootstrap payoff: fewer nodes to reach
      the train solutions). Measured on the full-depth run, not the shallow one, where a larger
      library merely considers more per depth.
    * ``enabled`` — the train tasks a *shallow* budget newly reaches with the abstraction.
    """
    _, base_considered = _restrict(deep_base, train_ids)
    _, aug_considered = _restrict(deep_augmented, train_ids)
    base_solved, _ = _restrict(shallow_base, train_ids)
    aug_solved, _ = _restrict(shallow_augmented, train_ids)
    return Usefulness(
        speedup=speedup_ratio(base_considered, aug_considered),
        enabled=aug_solved - base_solved,
    )
