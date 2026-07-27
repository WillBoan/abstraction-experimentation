"""Depth sandwich (D): the tractability claims, every one anchored at the budget its LEVEL runs at.

The sandwich is two-sided. *Affordable*: every intended jump, and the top over ``L_k``, must be in
REACH. *Intractable*: skipping any rung -- and the raw top unfolded to the floor -- must NOT be.
Both sides are stated in ``min_depth_limit`` (the smallest budget that reaches a program), which
equals ``compositional_depth`` for a first-order template and exceeds it when a lambda body needs
its own descended budget.

The budget each claim is read against is ``CheckContext.limit_at(level)``, never one pinned number:
a claim about rung ``i`` is a claim about the ``L_{i-1}`` search, and under the default DERIVED
depth schedule (``spec.DepthScheduleMode``) that search runs at rung ``i``'s own ``jump_needs``.
Under ``PINNED`` every level returns the same value and these checks read exactly as they did
before. The consequence worth naming: DERIVED satisfies ``jump-affordable`` and
``top-affordable-with-ladder`` BY CONSTRUCTION -- the budget is derived from the need those checks
test -- so under that regime they report rather than gate, and ``double-jump-intractable`` (the
per-rung sandwich, ``jump_needs < double_jump_needs``) is what a rung can still fail.

Both sides are also stated over the programs the ladder's searches will ACTUALLY run, never over
the rung templates: a rung's own bound comes from its DEMONSTRATION TARGETS, and a consumer's from
its (``CheckContext.consumer_targets``). The two readings coincide whenever every demonstration is
a full solution, and diverge exactly where one WRAPS its rung -- which the template reading missed
in both directions at once, under-claiming affordability and under-claiming the double-jump.

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
from arc_lab.program_search.substrate.abstraction import unfold_program
from arc_lab.program_search.substrate.program import Program


class JumpAffordable(LadderCheck):
    """Every rung's jump must be in REACH at the pinned ``depth_limit`` -- where "the jump" is the
    program the WAKE searches for, not the rung template.

    The two differ whenever a demonstration WRAPS its rung rather than being it. A rung returning a
    non-Grid value (Mask / Int / Offset / Coord) **must** be wrapped, since a task solution has to
    produce a Grid, so its demo costs ``d_i + (wrapper depth - 1)``. Measured on the template, a
    ladder can look affordable on every rung while every one of its demonstrations is structurally
    unreachable -- the climb then censors uniformly and the probe reports "not affordable" with no
    indication of why. (That failure shipped once, as the separate ``demo-affordable`` check;
    ``RungShape.jump_needs`` is now demo-sourced, so the two are one claim again.)

    Invisible to the whole al1-al20 batch: those ladders are Grid-valued and demoed as full
    solutions (wrapper depth 1), where the demo target IS the template. It bites the moment a
    ladder ladders BELOW the Grid type.
    """

    code = "jump-affordable"
    category = Category.DEPTH
    stage = CheckStage.STRUCTURAL
    summary = "Every rung's demonstrations are in reach over L_{i-1} at that level's depth_limit."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        for shape in ctx.rung_shapes:
            source = (
                f"demo `{shape.deepest_demonstration}`"
                if shape.deepest_demonstration is not None
                else "template (no demonstrations declared)"
            )
            limit = ctx.limit_at(shape.level - 1)
            yield self.finding(
                shape.jump_needs <= limit,
                f"{source} needs depth_limit {shape.jump_needs} (d={shape.jump_depth}) "
                f"over L_{shape.level - 1}, have {limit}",
                subject=shape.name,
            )


class ProperComposition(LadderCheck):
    """A rung is a PROPER composition over ``L_{i-1}``. A depth-1 template is a bare primitive
    already in that library, so it belongs to a lower rung and buys no depth.

    Stated on the TEMPLATE, deliberately: this is a claim about what sleep has to mint, and a
    wrapper in a demonstration cannot make a bare primitive into a real abstraction.
    """

    code = "proper-composition"
    category = Category.DEPTH
    stage = CheckStage.STRUCTURAL
    summary = "Every rung composes over the layer below rather than restating a bare primitive."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        for index, shape in enumerate(ctx.rung_shapes):
            yield self.finding(
                shape.template_depth >= 2,
                f"template depth {shape.template_depth}: a rung must compose over L_{index}, "
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
            limit = ctx.limit_at(rung.level - 1)
            yield self.finding(
                need > limit,
                f"skipping it reaches `{cid}` at depth_limit {need} "
                f"(inlined depth {compositional_depth(shallow)}), must exceed {limit}",
                subject=rung.name,
            )


class TopAffordableWithLadder(LadderCheck):
    code = "top-affordable-with-ladder"
    category = Category.DEPTH
    stage = CheckStage.STRUCTURAL
    summary = "Every top reference solution is in reach over L_k at the pinned depth_limit."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        limit = ctx.limit_at(ctx.k)
        for solution, d_top in zip(ctx.spec.top.reference_solutions, ctx.top_depths, strict=True):
            need = min_depth_limit(solution)
            yield self.finding(
                need <= limit,
                f"top over L_{ctx.k} needs depth_limit {need} (d={d_top}), have {limit}",
            )


class ClimbBudgetCoversTop(LadderCheck):
    """The pinned ``budget.depth_limit`` must cover the derived schedule's maximum, because the
    CLIMB searches at the pinned value. The chain is immune (it runs the per-level derived
    schedule), so a pinned value below the deepest level's need leaves the goal **structurally
    inexpressible to the learner at any budget**: the climb converges "cleanly", recovers every
    rung, and never solves the top task -- with nothing saying so.

    Shipped three times before this check existed (2026-07-27): ``dae9d2b5-split-asym-lean``
    (pinned 2, top depth 3, climb never solved its top) and both NOR ``-halves`` members (pinned
    3, top depth 4). Under ``PINNED`` schedule mode the schedule is uniform at the pinned value,
    so this passes trivially -- ``al10-skippable`` is unaffected.

    **Warning, not error, deliberately**: whether goal-reachability should GATE admission is an
    open design decision (the report's ``top_reachable`` block surfaces the empirical fact); this
    static form names the misconfiguration the moment it is authored.
    """

    code = "climb-budget-covers-top"
    category = Category.DEPTH
    stage = CheckStage.STRUCTURAL
    default_severity = "warn"
    summary = "The pinned depth_limit (the climb's search budget) covers the derived schedule."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        need = max(ctx.depth_schedule)
        yield self.finding(
            ctx.ref_limit >= need,
            f"pinned depth_limit {ctx.ref_limit} is below the derived schedule's max {need}: "
            "the climb searches at the pinned value, so the deepest level's target is "
            "structurally out of the learner's reach",
        )


class TopUsesTopRung(LadderCheck):
    """The Top Rung's whole definition: its solutions USE the top bridging rung as a fragment. A
    top that never calls ``r_k`` isn't standing on the ladder at all.

    ``rungs[-1]`` here is a LEVEL read and deliberately stays one: the claim is about the ladder's
    HEIGHT (the top must reach the full climb, not stop partway), which is a level property. On a
    DAG with independent branches every branch's tip is still required to be called -- the last
    level is the one that cannot be reached without everything below it having a consumer, which
    ``rung-referenced`` enforces separately.
    """

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
    summary = "No top solution is reachable from the bare floor at that level's depth_limit."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        # The bare floor IS `L_0`, so this is stated at level 0's budget -- the one the chain's
        # floor search, which carries the top tasks alongside rung 1's, actually runs at.
        limit = ctx.limit_at(0)
        for unfolded, d_raw in zip(ctx.unfolded_top, ctx.raw_depth_profile, strict=True):
            need = min_depth_limit(unfolded)
            yield self.finding(
                need > limit,
                f"d_raw={d_raw} needs depth_limit {need}, must exceed {limit}",
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
        limit = ctx.limit_at(ctx.k - 1)
        for skipped in ctx.skipped_top:
            need = min_depth_limit(skipped)
            yield self.finding(
                need > limit,
                f"top over L_{ctx.k - 1} depth {compositional_depth(skipped)} needs depth_limit "
                f"{need}, must exceed {limit}",
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
        # Targets are each rung's CONSUMER TARGETS, unfolded to the floor -- the same DAG
        # generalisation `double-jump-intractable` makes, over the same search-side programs. A
        # consumer id is either a higher rung's name or `top:<task_id>`; top consumers are
        # relabelled to the bare task id so the `probe_inputs` lookup (keyed by rung name or top
        # task id) resolves. Several demonstrations of one consumer share its id, so identical
        # unfolds are deduped -- a repeated verdict would just be the same conviction twice.
        rung_consumers = []
        for rung in ctx.rungs:
            targets: list[tuple[str, Program]] = []
            for cid, prog in ctx.consumer_targets[rung.name]:
                if cid.startswith("top:"):
                    task_id = cid[len("top:") :]
                    if task_id in ctx.unfolded_by_id:
                        pair = (task_id, ctx.unfolded_by_id[task_id])
                    else:
                        continue
                else:
                    pair = (cid, unfold_program(prog, ctx.full_lib))
                if pair not in targets:
                    targets.append(pair)
            rung_consumers.append((rung.name, targets))
        yield from self.stamp(
            rewrite_verdicts(
                rung_consumers,
                ctx.libraries,
                [ctx.limit_at(rung.level - 1) for rung in ctx.rungs],
                ctx.probe_inputs,
            )
        )
