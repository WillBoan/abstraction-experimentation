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
from arc_lab.solvers.dsl.substrate.program import Program


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


def rewrite_library_definitions(library: Library, name: str, template: Program) -> Library:
    """Fold occurrences of the abstraction ``name`` (defined by ``template``) into *other* learned
    definitions — library refactoring: compress the library, not just the corpus.

    The fold replaces a subtree with an equivalent call, so each primitive's behavior is preserved;
    its ``impl`` is rebuilt against ``library`` (which must already contain ``name``). This is the
    capability the corpus-only greedy loop lacks — the proposer walks call-sites, never definitions,
    so a shared factor buried in a definition can never otherwise be re-mined.
    """
    rebuilt: list[Primitive] = []
    changed = False
    for prim in library.primitives:
        if prim.template is None or prim.name == name:
            rebuilt.append(prim)
            continue
        folded = rewrite_with(prim.template, name, template)
        if folded == prim.template:
            rebuilt.append(prim)
        else:
            rebuilt.append(make_abstraction(prim.name, folded, library))
            changed = True
    if not changed:
        return library
    return Library(name=library.name, primitives=tuple(rebuilt), version=library.version + 1)


class RefactoringSleep(SleepStrategy):
    """Two-phase sleep: mine the corpus, then **refactor the library's own definitions**.

    **A labelled first-order stopgap.** The clean, single-pass "Stitch mines the corpus" *is* real —
    but only higher-order: Stitch emits the general reflect-across-a-*perceived*-dimension idiom
    ``(sub (sub (#1 input) #0) 1)`` with the perceiver ``#1`` as a *function* argument, which the
    first-order substrate cannot represent or consume yet (that unlocks in the higher-order phase).
    In first-order, mining the lambda-bearing corpus with Stitch yields only partial-applications and
    a *width/height-specialised* mirror — unusable. So this splits the work as a stopgap:

    Phase 1 (corpus) reuses the greedy machinery with ``corpus_proposer`` — the in-house, bound-var-safe
    proposer that soundly mines *closed* idioms (the read-bodies) from lambda-bearing wake programs, a
    first-order strength. Phase 2 (refactor) feeds those minted *definitions* to ``refactor_proposer``
    and adopts the shared factor that most lowers ``metric``, rewriting the definitions to use it. Stitch
    is the refactor engine wired in here: it *antiunifies* the differing perceiver into the general
    (first-order, search-composable) ``mirror_index``. This refactor is **not** intrinsically Stitch's —
    the in-house ``FrequentSubtree`` antiunifies too and would recover ``mirror_index`` if fed the same
    definitions (EXPERIMENTS.md records exactly this). The load-bearing seam is *call-sites vs
    definitions*: phase 1 mines call-sites, where the shared factor is still split across concrete
    perceivers; it surfaces only once the *definitions* are refactored, which is phase 2's job. Stitch
    invents; our ``metric`` governs (full cost control). Superseded once higher-order Stitch mines the
    corpus in one pass.
    """

    def __init__(
        self,
        corpus_proposer: AbstractionProposer,
        refactor_proposer: AbstractionProposer,
        *,
        selector: AbstractionSelector | None = None,
        metric: CompressionMetric | None = None,
        name_prefix: str = "abs",
    ) -> None:
        self.corpus_proposer = corpus_proposer
        self.refactor_proposer = refactor_proposer
        self.selector = selector or GreedyMDL()
        self.metric = metric or CompressionMetric()
        self.name_prefix = name_prefix

    def run(self, corpus: list[CorpusEntry], library: Library, start_index: int) -> SleepOutcome:
        # Phase 1 — corpus mining (the historical greedy behavior).
        phase1 = GreedyMDLSleep(
            self.corpus_proposer,
            selector=self.selector,
            metric=self.metric,
            name_prefix=self.name_prefix,
        ).run(corpus, library, start_index)
        library, corpus = phase1.library, phase1.corpus
        added = list(phase1.added)
        index = start_index + len(added)

        # Phase 2 — library refactoring: mine shared factors across the minted definitions.
        while True:
            best = self._refactor_select(corpus, library)
            if best is None:
                break
            name = f"{self.name_prefix}{index}"
            index += 1
            primitive = make_abstraction(name, best, library)
            library = library.extended(name=f"{library.name}+{name}", extra=(primitive,))
            corpus = [(task, rewrite_with(program, name, best)) for task, program in corpus]
            library = rewrite_library_definitions(library, name, best)
            added.append(primitive)

        score = self.metric.describe(corpus, library).total
        return SleepOutcome(library=library, added=tuple(added), corpus=corpus, score=score)

    def _refactor_select(self, corpus: list[CorpusEntry], library: Library) -> Program | None:
        """The factor mined from the definitions that most lowers DL when folded into them."""
        definitions = [p.template for p in library.primitives if p.template is not None]
        if len(definitions) < 2:  # nothing to refactor a shared factor across
            return None
        existing = {p.template for p in library.primitives if p.template is not None}
        best: Program | None = None
        best_dl = self.metric.describe(corpus, library).total
        for i, template in enumerate(self.refactor_proposer.propose(definitions, library)):
            if template in existing:
                continue
            probe = f"__ref{i}"
            probe_lib = library.extended(
                name="probe", extra=(make_abstraction(probe, template, library),)
            )
            probe_lib = rewrite_library_definitions(probe_lib, probe, template)
            probe_corpus = [(t, rewrite_with(p, probe, template)) for t, p in corpus]
            dl = self.metric.describe(probe_corpus, probe_lib).total
            if dl < best_dl:
                best_dl = dl
                best = template
        return best
