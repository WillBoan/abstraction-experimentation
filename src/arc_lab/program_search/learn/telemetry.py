"""Sleep-cost telemetry: cheap deterministic counters for one sleep phase's work.

Wake cost is measured in ``considered`` candidates (``search/tracking.py``); sleep has no such
native unit, so these give the amortization accounting a denominator on the learning side. A
mutable :class:`SleepCounters` is threaded through ``LearnEngine.run`` -> ``AbstractionSelector.
select`` -> ``AbstractionProposer.propose`` (an additive keyword arg, mirroring how a
``SearchTracker`` is threaded into the search engine) and its totals ride out on the
``LearnOutcome``. Telemetry only — never part of run identity.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SleepCounters:
    """Running totals for one ``LearnEngine.run`` (accumulated across its selection steps)."""

    #: Templates proposed across all selection steps (the raw ``propose`` output, pre-dedup).
    proposal_count: int = 0
    #: Pairs attempted in the antiunify ``combinations(_, 2)`` loops (each one an LGG attempt,
    #: whether or not it yields a usable template).
    antiunify_pair_count: int = 0
