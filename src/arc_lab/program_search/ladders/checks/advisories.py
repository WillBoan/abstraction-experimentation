"""Advisories (A): shape observations that are not defects.

Everything here is a WARN by construction. Each names something that is legitimate on purpose in
some ladders and accidental in others -- a pure telescope, a lambda-bearing template, a floor
broader than the spine -- so the check reports the fact and leaves the verdict to the author.
"""

from __future__ import annotations

from collections.abc import Iterator

from arc_lab.program_search.ladders.checks.base import Category, CheckStage, LadderCheck
from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.shape import LintFinding
from arc_lab.program_search.search.search_engine import BRANCHING_ENTRY
from arc_lab.program_search.substrate.program import Apply, If, PrimRef, Program


class NotAllTelescope(LadderCheck):
    """Does any rung recombine (fan-in > 1), or is the whole ladder a pure telescope?"""

    code = "not-all-telescope"
    category = Category.ADVISORY
    stage = CheckStage.STRUCTURAL
    default_severity = "warn"
    summary = "At least one rung recombines rather than piping a single lower-rung call."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        yield self.finding(
            any(shape.fan_in > 1 for shape in ctx.rung_shapes),
            "every rung has fan-in 1 (a pure telescope)",
        )


class NoLambdaInTemplates(LadderCheck):
    """The depth checks are EXACT for a lambda-bearing template (they are stated in
    ``min_depth_limit``, which accounts for the descended body budget). What stays advisory is the
    thing no depth function can express: a higher-order call nested under a wrapper can have its
    lambda body filtered out by example propagation, making it unreachable at ANY budget (measured
    2026-07-22 -- see ``analysis/depth.py``)."""

    code = "no-lambda-in-templates"
    category = Category.ADVISORY
    stage = CheckStage.STRUCTURAL
    default_severity = "warn"
    summary = "No rung template contains a lambda (whose reachability depth cannot certify)."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        if not any(shape.involves_lambda for shape in ctx.rung_shapes):
            return  # nothing to say: this advisory speaks only when a Lam is present
        yield self.finding(
            False,  # reached only when a template does carry a Lam
            "a rung template contains a Lam: depth claims hold, but a higher-order call that "
            "is not at the root of its solution may be unreachable at any depth_limit",
        )


class FloorFullyExercised(LadderCheck):
    """Every floor primitive should be exercised by something the ladder states.

    A warning, not an error: a floor is sometimes deliberately broader than the spine (al4 ships a
    realistic mask algebra). But an *accidental* dead primitive is not free -- it widens the round-0
    leaf set for every task, inflating the very vocabulary tax the batch is trying to attribute.
    """

    code = "floor-fully-exercised"
    category = Category.ADVISORY
    stage = CheckStage.STRUCTURAL
    default_severity = "warn"
    summary = "Every floor primitive is used by some rung, demonstration, distractor or top."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        exercised = _exercised_primitives(
            [*ctx.unfolded_templates, *(sol for _, sol in ctx.unfolded_stated)]
        )
        idle = [p.name for p in ctx.spec.floor().primitives if p.name not in exercised]
        yield self.finding(
            not idle,
            f"floor primitives no rung, demonstration, distractor or top solution uses: {idle}",
        )


def _exercised_primitives(roots: list[Program]) -> set[str]:
    """Every primitive name the given programs use, branching included.

    Distinct-id traversal: shared subtrees of a deep unfold are visited once, so al14's millions of
    node occurrences cost a few hundred visits. An ``If`` credits the floor's ``if`` summoner --
    branching is summoned, never applied, so without this a conditional floor would read as dead
    vocabulary.
    """
    exercised: set[str] = set()
    visited: set[int] = set()
    stack = list(roots)
    while stack:
        node = stack.pop()
        if id(node) in visited:
            continue
        visited.add(id(node))
        if isinstance(node, Apply):
            exercised.add(node.primitive)
        elif isinstance(node, PrimRef):
            exercised.add(node.name)  # used as a first-class function value
        elif isinstance(node, If):
            exercised.add(BRANCHING_ENTRY)
        stack.extend(node.children())
    return exercised
