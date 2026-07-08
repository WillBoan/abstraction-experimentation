"""The *sleep* step as a pluggable strategy: turn a solved corpus into named abstractions.

The wake-sleep loop's sleep phase — invent abstraction candidates, decide which earn a name,
mint them, and fold them into the library — is lifted here behind :class:`SleepStrategy` so the
whole invention + governance + rewrite unit can be swapped and compared: the in-house greedy-MDL
machinery, an external engine (Stitch), a library-refactoring pass, .... The loop
(:func:`~...loop.learn`) owns only the wake step and the cross-generation guards; the strategy
owns *how* abstractions are found and returns the scalar the loop compares to decide convergence,
so the loop never needs to know the governance objective.

:class:`GreedyMDLSleep` is the default and preserves the historical sleep behavior exactly: it
greedily adds the single best-compressing candidate (an :class:`AbstractionSelector` over an
:class:`AbstractionProposer`), rewriting the corpus each step until no candidate compresses, then
scores the result with its :class:`CompressionMetric`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from arc_lab.solvers.dsl.analysis.compression import CompressionMetric, CorpusEntry
from arc_lab.solvers.dsl.learn.antiunify import AbstractionProposer, rewrite_with
from arc_lab.solvers.dsl.learn.selection import AbstractionSelector, GreedyMDL
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
from arc_lab.solvers.dsl.substrate.library import Library, Primitive


@dataclass(frozen=True, slots=True)
class SleepOutcome:
    """The result of one sleep step.

    ``score`` is the loop's convergence signal (lower is better) — the strategy's own measure of
    the outcome, so :func:`~...loop.learn` compares generations without knowing the objective.
    """

    library: Library
    added: tuple[Primitive, ...]
    corpus: list[CorpusEntry]
    score: float


class SleepStrategy(ABC):
    """Grow a library from a solved corpus in one sleep step."""

    @abstractmethod
    def run(self, corpus: list[CorpusEntry], library: Library, start_index: int) -> SleepOutcome:
        """Invent + govern + fold abstractions; ``start_index`` seeds unique abstraction names."""


class GreedyMDLSleep(SleepStrategy):
    """Greedily add the single best-compressing abstraction, rewrite, repeat until dry.

    The historical sleep behavior, now a strategy: an :class:`AbstractionSelector` (default
    :class:`GreedyMDL`) picks the most-compressing candidate from ``proposer`` each step; the
    score is the corpus's two-part description length under ``metric``.
    """

    def __init__(
        self,
        proposer: AbstractionProposer,
        *,
        selector: AbstractionSelector | None = None,
        metric: CompressionMetric | None = None,
        name_prefix: str = "abs",
    ) -> None:
        self.proposer = proposer
        self.selector = selector or GreedyMDL()
        self.metric = metric or CompressionMetric()
        self.name_prefix = name_prefix

    def run(self, corpus: list[CorpusEntry], library: Library, start_index: int) -> SleepOutcome:
        added: list[Primitive] = []
        index = start_index
        while True:
            best = self.selector.select(corpus, library, self.proposer, self.metric)
            if best is None:
                break
            name = f"{self.name_prefix}{index}"
            index += 1
            primitive = make_abstraction(name, best, library)
            library = library.extended(name=f"{library.name}+{name}", extra=(primitive,))
            corpus = [(task, rewrite_with(program, name, best)) for task, program in corpus]
            added.append(primitive)
        score = self.metric.describe(corpus, library).total
        return SleepOutcome(library=library, added=tuple(added), corpus=corpus, score=score)
