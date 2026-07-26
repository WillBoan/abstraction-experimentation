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
                subject=shape.name,
            )


class DemoAffordable(LadderCheck):
    """Every rung's own DEMONSTRATION must be in reach at the pinned ``depth_limit``.

    ``jump-affordable`` measures the rung TEMPLATE, but the wake at rung ``i`` searches for the
    demonstrating task's solution over ``L_{i-1}`` -- and that is a different program whenever the
    demo wraps the rung rather than being it. A rung returning a non-Grid value (Mask / Int /
    Offset / Coord) **must** be wrapped, since a task solution has to produce a Grid, so its demo
    costs ``d_i + (wrapper depth - 1)``. A ladder can therefore pass ``jump-affordable`` on every
    rung while every one of its demonstrations is structurally unreachable -- the climb then
    censors uniformly and the probe reports "not affordable" with no indication of why.

    Invisible to the whole al1-al20 batch: those ladders are Grid-valued and demoed as full
    solutions (wrapper depth 1), where the demo target IS the template and this check is exactly
    ``jump-affordable``. It bites the moment a ladder ladders BELOW the Grid type.
    """

    code = "demo-affordable"
    category = Category.DEPTH
    stage = CheckStage.STRUCTURAL
    summary = "Every rung's demonstrations are in reach over L_{i-1} at the pinned depth_limit."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        for rung in ctx.rungs:
            for task_id, target in ctx.demo_targets[rung.name]:
                need = min_depth_limit(target)
                yield self.finding(
                    need <= ctx.ref_limit,
                    f"demo `{task_id}` needs depth_limit {need} "
                    f"(d={compositional_depth(target)}) over L_{rung.level - 1}, "
                    f"have {ctx.ref_limit}",
                    subject=rung.name,
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
                subject=shape.name,
            )


class DoubleJumpIntractable(LadderCheck):
    """Skipping a rung inlines it into EVERY program that calls it. The rung earns its place iff
    the SHALLOWEST consumer stays out of reach (if the shallowest exceeds ``depth_limit``, all do).

    For a chain the only consumer is the next rung, so this is byte-identical to the old adjacency
    check; for a DAG it catches a non-adjacent or plural consumer the successor-only form missed.
    The TOP layer's necessity relative to ``r_k`` is ``top-double-jump-intractable`` -- per top
    solution, and finer-grained -- so top consumers are excluded here.

    **Warning, not error** (severity relaxed 2026-07-24, the certificate-profile reframe): this is
    skip-freeness -- the sandwich's constraint 2, a *simplification*, not an admission requirement
    (CERTIFICATE-PROFILE-2026-07-24.md). A skippable rung is a data point about a cut placement,
    recorded in the per-rung verdict profile, not a reason the ladder may not exist. The real gates
    stay errors: ``jump-affordable`` (constraint 1, near-fundamental) and ``raw-intractable`` (the
    whole-ladder "does this measure anything" claim). Mixed-depth ladders may now lint-clean and are
    gated by the probe's joint depth+considered budget.
    """

    code = "double-jump-intractable"
    category = Category.DEPTH
    stage = CheckStage.STRUCTURAL
    default_severity = "warn"
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
                subject=rung.name,
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
    """The top layer's skip-freeness relative to ``r_k``. **Warning, not error** for the same
    reason as :class:`DoubleJumpIntractable` (constraint 2, the certificate-profile reframe): a
    top reachable without the top rung is a skippable-top data point, gated by the certificate's
    ``no_skip_paths`` and by ``raw-intractable`` (whole-ladder), not by this static lint."""

    code = "top-double-jump-intractable"
    category = Category.DEPTH
    stage = CheckStage.STRUCTURAL
    default_severity = "warn"
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
        # Targets are each rung's CONSUMERS, unfolded to the floor -- the same DAG generalisation
        # `double-jump-intractable` already makes. A consumer id is either a higher rung's name or
        # `top:<task_id>`; top consumers are relabelled to the bare task id so the `probe_inputs`
        # lookup (keyed by rung name or top task id) resolves.
        unfolded_rungs = {
            rung.name: unfolded
            for rung, unfolded in zip(ctx.rungs, ctx.unfolded_templates, strict=True)
        }
        rung_consumers = []
        for rung in ctx.rungs:
            targets = []
            for cid, _ in ctx.consumer_programs[rung.name]:
                if cid.startswith("top:"):
                    task_id = cid[len("top:") :]
                    if task_id in ctx.unfolded_by_id:
                        targets.append((task_id, ctx.unfolded_by_id[task_id]))
                elif cid in unfolded_rungs:
                    targets.append((cid, unfolded_rungs[cid]))
            rung_consumers.append((rung.name, targets))
        yield from self.stamp(
            rewrite_verdicts(
                rung_consumers,
                ctx.libraries,
                ctx.ref_limit,
                ctx.probe_inputs,
            )
        )
