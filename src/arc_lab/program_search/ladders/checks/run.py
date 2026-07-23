"""``lint_spec``: run the plan over one ladder and assemble its :class:`~..shape.LadderShape`.

The whole lint is this: build the context, walk ``CHECK_PLAN``, collect what each check yields,
and pair the findings with the derived shape quantities the context already computed. Gating is a
single ``stage`` comparison -- a ``CORPUS`` check on a corpus-less draft is named in
``skipped_checks``, never silently dropped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from arc_lab.program_search.ladders.checks.base import CheckStage
from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.checks.plan import CHECK_PLAN
from arc_lab.program_search.ladders.shape import LadderShape, LintFinding

if TYPE_CHECKING:
    from arc_lab.program_search.ladders.spec import LadderSpec


def lint_spec(spec: LadderSpec, *, corpus_backed: bool = True) -> LadderShape:
    """Run every check in :data:`~.plan.CHECK_PLAN` and derive the ladder's static shape.

    ``corpus_backed=False`` runs the STRUCTURAL tier only -- the checks whose inputs are templates,
    stated solutions, demonstration kinds and config, none of which need the task grids. It is what
    lets a *draft* over assumed primitives (which has no evaluable corpus) be linted at all.
    """
    ctx = CheckContext(spec, corpus_backed=corpus_backed)
    findings: list[LintFinding] = []
    skipped: list[str] = []
    for check in CHECK_PLAN:
        if check.stage is CheckStage.CORPUS and not corpus_backed:
            skipped.append(check.code)
            continue
        findings.extend(check.run(ctx))
    return LadderShape(
        height=ctx.k + 1,
        raw_depth_profile=ctx.raw_depth_profile,
        rungs=ctx.rung_shapes,
        validity_window=ctx.validity_window,
        is_chain=ctx.is_chain,
        findings=tuple(findings),
        skipped_checks=tuple(skipped),
    )
