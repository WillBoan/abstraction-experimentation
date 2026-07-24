"""Learnability (L): can the configured machinery actually MINT the rung it is shown?

A ladder can be perfectly shaped and still stall, for two independent reasons: the configured
proposer may not be able to serve the demonstration kinds the tasks provide, or greedy-MDL
governance may refuse the mint because it does not pay for itself.
"""

from __future__ import annotations

from collections.abc import Iterator

from arc_lab.program_search.analysis.compression import CompressionMetric, SolvedTask
from arc_lab.program_search.ladders.checks.base import Category, CheckStage, LadderCheck
from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.shape import LintFinding
from arc_lab.program_search.ladders.spec import DemonstrationKind
from arc_lab.program_search.substrate.abstraction import unfold_program

#: What each proposer (by class name -- avoids importing the dep-gated Stitch shim) can serve.
#: Keyed to :class:`~..spec.DemonstrationKind`, which IS the section 2 mapping: the demonstration
#: kind a rung is shown at is exactly the proposer it requires.
_PROPOSER_CAPABILITIES: dict[str, frozenset[DemonstrationKind]] = {
    "AntiunifyPairs": frozenset({DemonstrationKind.FULL_SOLUTION}),
    "FrequentSubtree": frozenset(
        {DemonstrationKind.FULL_SOLUTION, DemonstrationKind.FRAGMENT_IDENTICAL}
    ),
    "TypeScopedFrequentSubtree": frozenset(
        {DemonstrationKind.FULL_SOLUTION, DemonstrationKind.FRAGMENT_IDENTICAL}
    ),
    "SearchScopedFrequentSubtree": frozenset(
        {DemonstrationKind.FULL_SOLUTION, DemonstrationKind.FRAGMENT_IDENTICAL}
    ),
    "StitchProposer": frozenset(DemonstrationKind),
}


class ProposerCompat(LadderCheck):
    """The configured proposer must be able to serve every demonstration kind the rung is shown at.

    Severity is itself a verdict here: an unrecognised proposer is a WARN (its capability is not
    statically known), never an error -- the check reports what it cannot see rather than guessing.
    """

    code = "proposer-compat"
    category = Category.LEARNABILITY
    stage = CheckStage.STRUCTURAL
    summary = "The configured proposer can serve every demonstration kind the rungs are shown at."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        proposer = getattr(
            getattr(ctx.spec.reference_config.learn, "learn_engine", None), "proposer", None
        )
        provided = (
            _PROPOSER_CAPABILITIES.get(type(proposer).__name__) if proposer is not None else None
        )
        for rung in ctx.rungs:
            if provided is None:
                yield self.finding(
                    True,  # an unknown capability is reported, never assumed broken
                    "proposer capability not statically known",
                    subject=rung.name,
                    severity="warn",
                )
                continue
            kinds = {demo.kind for demo in rung.demonstrations}
            yield self.finding(
                kinds <= provided,
                f"{sorted(k.value for k in kinds - provided)} unservable by "
                f"{type(proposer).__name__}",
                subject=rung.name,
            )


class MdlBreakEven(LadderCheck):
    """Minting a rung must lower the description length of the very solutions that demonstrate it,
    under the ladder's OWN configured metric -- otherwise greedy-MDL governance refuses the mint and
    the climb stalls there.

    A per-rung-demonstrations PROXY for whole-corpus governance, conservative by design: real
    governance scores every solution at the iteration plus the library term, so a rung passing here
    can still be refused -- never the reverse claim.
    """

    code = "mdl-break-even"
    category = Category.LEARNABILITY
    stage = CheckStage.CORPUS  # the score is taken over the demonstrating tasks resolved in `by_id`
    summary = "Minting each rung pays for itself in bits on its own demonstrations."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        metric = getattr(
            getattr(ctx.spec.reference_config.learn, "learn_engine", None), "metric", None
        )
        if metric is None:
            metric = CompressionMetric()
        for level, rung in enumerate(ctx.rungs, start=1):
            entries = [
                (ctx.by_id[demo.task_id], demo.solution)
                for demo in rung.demonstrations
                if demo.task_id in ctx.by_id
            ]
            if not entries:
                continue
            below, above = ctx.libraries[level - 1], ctx.libraries[level]
            folded = [SolvedTask(annotated=a, program=p) for a, p in entries]
            unminted = [
                SolvedTask(
                    annotated=a, program=unfold_program(p, above, expand=frozenset({rung.name}))
                )
                for a, p in entries
            ]
            gain = metric.describe(unminted, below).total - metric.describe(folded, above).total
            yield self.finding(
                gain > 0,
                f"minting it costs {-gain:.1f} bits more than it saves on its own "
                f"{len(entries)} demonstration(s), so governance will refuse it",
                subject=rung.name,
            )
