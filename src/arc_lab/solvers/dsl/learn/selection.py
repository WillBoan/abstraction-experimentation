"""Governance: choosing which proposed template earns a place in the library.

The *sleep* step proposes many abstraction candidates (see :mod:`antiunify`); governance is
the filter that decides which — if any — is worth minting. It is a distinct plug point from
invention: the same proposals can be governed greedily, by a beam over sets, or jointly, and
E3 showed governance is genuinely *plural* (greedy-over-a-flat-cost bloats where two-part MDL
does not). Lifting it behind :class:`AbstractionSelector` — as :mod:`antiunify` does for the
proposer — is what lets those strategies be swapped and compared in isolation.

:class:`GreedyMDL` is the default: it probes each candidate into a throwaway library, measures
the corpus's two-part description length, and returns the single template that lowers it most
(or ``None`` when none does — the loop's termination signal). The library-dedup guard here
(never re-mint a template already a primitive) is one of the two E3 hardening safeguards.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from arc_lab.solvers.dsl.analysis.compression import CompressionMetric, CorpusEntry
from arc_lab.solvers.dsl.learn.antiunify import AbstractionProposer, rewrite_with
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.program import Program


class AbstractionSelector(ABC):
    """Decide which proposed template (if any) the library should adopt this step."""

    @abstractmethod
    def select(
        self,
        corpus: list[CorpusEntry],
        library: Library,
        proposer: AbstractionProposer,
        metric: CompressionMetric,
    ) -> Program | None:
        """The template to adopt now, or ``None`` when no candidate is worth minting."""


class GreedyMDL(AbstractionSelector):
    """Add the single candidate that most reduces the corpus's two-part description length.

    TODO(alternatives): beam / joint selection over abstraction *sets* — greedy is myopic and
    cannot find candidates that only pay off together (see MACHINERY.md F4 'Beam / joint selection').
    """

    def select(
        self,
        corpus: list[CorpusEntry],
        library: Library,
        proposer: AbstractionProposer,
        metric: CompressionMetric,
    ) -> Program | None:
        # Dedup against the library: never re-mint a template we already have as a primitive
        # (the cross-generation duplication observed in E3, e.g. abs4 identical to abs1).
        existing = {p.template for p in library.primitives if p.template is not None}
        candidates = [
            template
            for template in proposer.propose([program for _, program in corpus], library)
            if template not in existing
        ]
        best_template: Program | None = None
        best_dl = metric.describe(corpus, library).total
        for i, template in enumerate(candidates):
            name = f"__probe{i}"
            probe_lib = library.extended(
                name="probe", extra=(make_abstraction(name, template, library),)
            )
            rewritten = [(task, rewrite_with(program, name, template)) for task, program in corpus]
            dl = metric.describe(rewritten, probe_lib).total
            if dl < best_dl:
                best_dl = dl
                best_template = template
        return best_template
