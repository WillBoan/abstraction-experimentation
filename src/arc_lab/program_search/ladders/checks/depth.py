"""Depth sandwich (D): the tractability claims, every one anchored at the reference budget.

The sandwich is two-sided. *Affordable*: every intended jump, and the top over ``L_k``, must be in
REACH at the pinned ``depth_limit``. *Intractable*: skipping any rung -- and the raw top unfolded
to the floor -- must NOT be. Both sides are stated in ``min_depth_limit`` (the smallest budget that
reaches a program), which equals ``compositional_depth`` for a first-order template and exceeds it
when a lambda body needs its own descended budget.

``rewrite-shallow`` is the sandwich's equational blind spot, closed: the depth checks measure the
INTENDED program, so a few known equations re-expressing the layer above a skipped rung shallowly
would go unseen (al7's ``tall4 == stack2(stack2 g)``).
"""

from __future__ import annotations

from collections.abc import Iterator

from arc_lab.program_search.analysis.depth import compositional_depth, min_depth_limit
from arc_lab.program_search.ladders import graph
from arc_lab.program_search.ladders.checks.base import Category, CheckStage, LadderCheck
from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.checks.evaluation import rewrite_verdicts
from arc_lab.program_search.ladders.shape import LintFinding


class JumpAffordable(LadderCheck):
    code = "jump-affordable"
    category = Category.DEPTH
    stage = CheckStage.STRUCTURAL
    summary = "Every rung template is in reach at the pinned depth_limit."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        for shape in ctx.rung_shapes:
            yield self.finding(
                shape.jump_needs <= ctx.ref_limit,
                f"needs depth_limit {shape.jump_needs} (d={shape.jump_depth}), have {ctx.ref_limit}",
                occurrence=shape.name,
            )


class ProperComposition(LadderCheck):
    """A rung is a PROPER composition over ``L_{i-1}``. A depth-1 template is a bare primitive
    already in that library, so it belongs to a lower rung and buys no depth."""

    code = "proper-composition"
    category = Category.DEPTH
    stage = CheckStage.STRUCTURAL
    summary = "Every rung composes over the layer below rather than restating a bare primitive."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        for index, shape in enumerate(ctx.rung_shapes):
            yield self.finding(
                shape.jump_depth >= 2,
                f"jump depth {shape.jump_depth}: a rung must compose over L_{index}, "
                "not restate a bare primitive",
                occurrence=shape.name,
            )


class DoubleJumpIntractable(LadderCheck):
    """Skipping a rung inlines it into EVERY program that calls it. The rung earns its place iff
    the SHALLOWEST consumer stays out of reach (if the shallowest exceeds ``depth_limit``, all do).

    For a chain the only consumer is the next rung, so this is byte-identical to the old adjacency
    check; for a DAG it catches a non-adjacent or plural consumer the successor-only form missed.
    The TOP layer's necessity relative to ``r_k`` is ``top-double-jump-intractable`` -- per top
    solution, and finer-grained -- so top consumers are excluded here.
    """

    code = "double-jump-intractable"
    category = Category.DEPTH
    stage = CheckStage.STRUCTURAL
    summary = "Skipping a rung leaves every higher rung out of reach at the pinned depth_limit."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        for rung in ctx.rungs:
            inlined = [
                (cid, prog)
                for cid, prog in ctx.inlined_consumers[rung.name]
                if not cid.startswith("top:")
            ]
            if not inlined:  # only top consumers: the top layer's own check owns this rung
                continue
            cid, shallow = min(inlined, key=lambda item: min_depth_limit(item[1]))
            need = min_depth_limit(shallow)
            yield self.finding(
                need > ctx.ref_limit,
                f"skipping it reaches `{cid}` at depth_limit {need} "
                f"(inlined depth {compositional_depth(shallow)}), must exceed {ctx.ref_limit}",
                occurrence=rung.name,
            )


class TopAffordableWithLadder(LadderCheck):
    code = "top-affordable-with-ladder"
    category = Category.DEPTH
    stage = CheckStage.STRUCTURAL
    summary = "Every top reference solution is in reach over L_k at the pinned depth_limit."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        for solution, d_top in zip(ctx.spec.top.reference_solutions, ctx.top_depths, strict=True):
            need = min_depth_limit(solution)
            yield self.finding(
                need <= ctx.ref_limit,
                f"top over L_{ctx.k} needs depth_limit {need} (d={d_top}), have {ctx.ref_limit}",
            )


class TopUsesTopRung(LadderCheck):
    """The Top Rung's whole definition: its solutions USE the top bridging rung as a fragment. A
    top that never calls ``r_k`` isn't standing on the ladder at all."""

    code = "top-uses-top-rung"
    category = Category.DEPTH
    stage = CheckStage.STRUCTURAL
    summary = "Every top reference solution calls the top bridging rung."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        top_rung = ctx.rungs[-1].name
        for solution in ctx.spec.top.reference_solutions:
            yield self.finding(
                graph.calls(solution, top_rung) >= 1,
                f"a top reference solution never calls {top_rung}",
            )


class RawIntractable(LadderCheck):
    code = "raw-intractable"
    category = Category.DEPTH
    stage = CheckStage.STRUCTURAL
    summary = "No top solution is reachable from the bare floor at the pinned depth_limit."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        for unfolded, d_raw in zip(ctx.unfolded_top, ctx.raw_depth_profile, strict=True):
            need = min_depth_limit(unfolded)
            yield self.finding(
                need > ctx.ref_limit,
                f"d_raw={d_raw} needs depth_limit {need}, must exceed {ctx.ref_limit}",
            )


class TopDoubleJumpIntractable(LadderCheck):
    code = "top-double-jump-intractable"
    category = Category.DEPTH
    stage = CheckStage.STRUCTURAL
    summary = "No top solution is reachable over L_{k-1} (with the top rung skipped)."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        for skipped in ctx.skipped_top:
            need = min_depth_limit(skipped)
            yield self.finding(
                need > ctx.ref_limit,
                f"top over L_{ctx.k - 1} depth {compositional_depth(skipped)} needs depth_limit "
                f"{need}, must exceed {ctx.ref_limit}",
            )


class RewriteShallow(LadderCheck):
    """Bounded equational skip-path detection: can the layer above a skipped rung be re-expressed
    over ``L_{i-1}`` within the pinned ``depth_limit``? Reported only after BEHAVIORAL confirmation
    on the target's own probe inputs. No witness (or any cap hit) is a silent pass -- this check can
    convict, never acquit."""

    code = "rewrite-shallow"
    category = Category.DEPTH
    stage = CheckStage.CORPUS  # witnesses are confirmed by evaluating on the tasks' train inputs
    summary = "No known equation re-expresses the layer above a skipped rung shallowly."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        yield from self.stamp(
            rewrite_verdicts(
                list(zip((rung.name for rung in ctx.rungs), ctx.unfolded_templates, strict=True)),
                [
                    (tid, ctx.unfolded_by_id[tid])
                    for tid in ctx.spec.top.task_ids
                    if tid in ctx.unfolded_by_id
                ],
                ctx.libraries,
                ctx.ref_limit,
                ctx.probe_inputs,
            )
        )
