"""The sleep interface (EXECUTION.md).

``LearnEngine.run`` is one *sleep*: it consumes the whole corpus's wake solutions at
once (cross-task compression needs the corpus in view) and returns a
:class:`LearnOutcome` — the grown library plus what happened (telemetry for the
per-iteration trace). The wake-sleep *loop* around it (iterations, early-stop, reset
policy) is not here — those are ``LearnSpec`` params in the run identity
(``execution/model/learn_spec.py``); sleep's internal governance (MDL threshold,
proposer choice) belongs on concrete engines, which are frozen dataclasses so the
whole engine hashes into the ``run_id`` via the component serde.

Concrete engines live in :mod:`engines`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arc_lab.program_search.analysis.compression import SolvedTask
    from arc_lab.program_search.substrate.library import Library, Primitive


@dataclass(frozen=True, slots=True)
class LearnOutcome:
    """The result of one sleep step.

    ``description_length`` is the corpus's two-part MDL under the grown library
    (lower is better) — the governance objective's value, *not* a task score
    (``score_task`` is the test-example scorer; unrelated).
    """

    library: Library
    added: tuple[Primitive, ...]
    #: The wake solutions re-expressed in the grown library — telemetry for the trace.
    rewritten: tuple[SolvedTask, ...]
    description_length: float
    #: Sleep-cost telemetry (``learn/telemetry.py``): total proposals seen and antiunify pairs
    #: attempted across this sleep's selection steps. Never part of run identity.
    proposal_count: int = 0
    antiunify_pair_count: int = 0

    @property
    def converged(self) -> bool:
        """True iff sleep added nothing — the loop's ``early_stop`` signal."""
        return not self.added


@dataclass(frozen=True, slots=True, kw_only=True)
class LearnEngine(ABC):
    """Sleep: grow the library from a whole corpus's wake solutions."""

    @abstractmethod
    def run(self, library: Library, solutions: tuple[SolvedTask, ...]) -> LearnOutcome:
        """One sleep: propose + govern + fold abstractions over the solved corpus."""
