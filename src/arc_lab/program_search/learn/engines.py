"""Concrete :class:`LearnEngine`\\ s — the sleep machinery.

One ``run`` is one *sleep*: invent abstraction candidates (an :class:`AbstractionProposer`),
decide which earn a name (an :class:`AbstractionSelector` under a :class:`CompressionMetric`),
mint them, fold them into the library, and return a :class:`LearnOutcome`. Engines are frozen
dataclasses: they sit inside ``LearnSpec`` inside ``Config``, so their parameters are run
identity, hashed via the component serde.

:class:`GreedyMDLLearnEngine` is stateless: its naming seed is derived from the library
(the next free ``absN`` index), and a sleep that adds nothing returns the library
unchanged — the ``LearnOutcome.converged`` signal the execution loop's ``early_stop``
reads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from arc_lab.program_search.analysis.compression import CompressionMetric, SolvedTask
from arc_lab.program_search.learn.antiunify import AbstractionProposer, rewrite_with
from arc_lab.program_search.learn.learn_engine import LearnEngine, LearnOutcome
from arc_lab.program_search.learn.selection import AbstractionSelector, GreedyMDL
from arc_lab.program_search.learn.telemetry import SleepCounters
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.program import Program


def _next_index(library: Library, prefix: str) -> int:
    """The next free ``{prefix}N`` naming index — derived from the library, not threaded state."""
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    taken = [
        int(match.group(1))
        for primitive in library.primitives
        if (match := pattern.match(primitive.name)) is not None
    ]
    return max(taken) + 1 if taken else 0


@dataclass(frozen=True, slots=True, kw_only=True)
class GreedyMDLLearnEngine(LearnEngine):
    """Greedily add the single best-compressing abstraction, rewrite, repeat until dry.

    An :class:`AbstractionSelector` (default :class:`GreedyMDL`) picks the most-compressing
    candidate from ``proposer`` each step; ``description_length`` is the corpus's two-part
    DL under ``metric``.
    """

    proposer: AbstractionProposer
    selector: AbstractionSelector = field(default_factory=GreedyMDL)
    metric: CompressionMetric = field(default_factory=CompressionMetric)
    name_prefix: str = "abs"

    def run(self, library: Library, solutions: tuple[SolvedTask, ...]) -> LearnOutcome:
        corpus = list(solutions)
        added: list[Primitive] = []
        counters = SleepCounters()
        index = _next_index(library, self.name_prefix)
        while True:
            best = self.selector.select(
                corpus, library, self.proposer, self.metric, counters=counters
            )
            if best is None:
                break
            name = f"{self.name_prefix}{index}"
            index += 1
            primitive = make_abstraction(name, best, library)
            library = library.extended(name=f"{library.name}+{name}", extra=(primitive,))
            corpus = [replace(st, program=rewrite_with(st.program, name, best)) for st in corpus]
            added.append(primitive)
        return LearnOutcome(
            library=library,
            added=tuple(added),
            rewritten=tuple(corpus),
            description_length=self.metric.describe(corpus, library).total,
            proposal_count=counters.proposal_count,
            antiunify_pair_count=counters.antiunify_pair_count,
        )


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


@dataclass(frozen=True, slots=True, kw_only=True)
class RefactoringLearnEngine(LearnEngine):
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

    corpus_proposer: AbstractionProposer
    refactor_proposer: AbstractionProposer
    selector: AbstractionSelector = field(default_factory=GreedyMDL)
    metric: CompressionMetric = field(default_factory=CompressionMetric)
    name_prefix: str = "abs"

    def run(self, library: Library, solutions: tuple[SolvedTask, ...]) -> LearnOutcome:
        # Phase 1 — corpus mining (the historical greedy behavior).
        phase1 = GreedyMDLLearnEngine(
            proposer=self.corpus_proposer,
            selector=self.selector,
            metric=self.metric,
            name_prefix=self.name_prefix,
        ).run(library, solutions)
        library, corpus = phase1.library, list(phase1.rewritten)
        added = list(phase1.added)
        # Accumulate onto phase 1's counts so the outcome carries the whole sleep's sleep-cost.
        counters = SleepCounters(
            proposal_count=phase1.proposal_count,
            antiunify_pair_count=phase1.antiunify_pair_count,
        )
        index = _next_index(library, self.name_prefix)

        # Phase 2 — library refactoring: mine shared factors across the minted definitions.
        while True:
            best = self._refactor_select(corpus, library, counters=counters)
            if best is None:
                break
            name = f"{self.name_prefix}{index}"
            index += 1
            primitive = make_abstraction(name, best, library)
            library = library.extended(name=f"{library.name}+{name}", extra=(primitive,))
            corpus = [replace(st, program=rewrite_with(st.program, name, best)) for st in corpus]
            library = rewrite_library_definitions(library, name, best)
            added.append(primitive)

        return LearnOutcome(
            library=library,
            added=tuple(added),
            rewritten=tuple(corpus),
            description_length=self.metric.describe(corpus, library).total,
            proposal_count=counters.proposal_count,
            antiunify_pair_count=counters.antiunify_pair_count,
        )

    def _refactor_select(
        self, corpus: list[SolvedTask], library: Library, *, counters: SleepCounters | None = None
    ) -> Program | None:
        """The factor mined from the definitions that most lowers DL when folded into them."""
        definitions = [p.template for p in library.primitives if p.template is not None]
        if len(definitions) < 2:  # nothing to refactor a shared factor across
            return None
        existing = {p.template for p in library.primitives if p.template is not None}
        best: Program | None = None
        best_dl = self.metric.describe(corpus, library).total
        proposed = self.refactor_proposer.propose(definitions, library, counters=counters)
        if counters is not None:
            counters.proposal_count += len(proposed)
        for i, template in enumerate(proposed):
            if template in existing:
                continue
            probe = f"__ref{i}"
            probe_lib = library.extended(
                name="probe", extra=(make_abstraction(probe, template, library),)
            )
            probe_lib = rewrite_library_definitions(probe_lib, probe, template)
            probe_corpus = [
                replace(st, program=rewrite_with(st.program, probe, template)) for st in corpus
            ]
            dl = self.metric.describe(probe_corpus, probe_lib).total
            if dl < best_dl:
                best_dl = dl
                best = template
        return best
