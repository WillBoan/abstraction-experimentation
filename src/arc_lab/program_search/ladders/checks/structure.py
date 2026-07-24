"""Structure (S): is this a ladder at all?

Levels, task resolution, alignment, demonstration counts, reachability and distinctness -- the
checks that ask whether the declared parts form a well-founded spine, before any depth claim is
weighed.
"""

from __future__ import annotations

from collections.abc import Iterator

from arc_lab.program_search.ladders.checks.base import Category, CheckStage, LadderCheck
from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.shape import LintFinding


class LevelsContiguous(LadderCheck):
    code = "levels-contiguous"
    category = Category.STRUCTURE
    stage = CheckStage.STRUCTURAL
    summary = "Rung levels are exactly 1..k, in order."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        levels = [rung.level for rung in ctx.rungs]
        yield self.finding(
            tuple(levels) == tuple(range(1, ctx.k + 1)), f"levels {levels} must be 1..{ctx.k}"
        )


class TopSolutionsAligned(LadderCheck):
    code = "top-solutions-aligned"
    category = Category.STRUCTURE
    stage = CheckStage.STRUCTURAL
    summary = "Every top task id has a reference solution, and vice versa."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        top = ctx.spec.top
        yield self.finding(
            len(top.task_ids) == len(top.reference_solutions),
            f"{len(top.task_ids)} top task ids vs {len(top.reference_solutions)} solutions",
        )


class MinTwoDemos(LadderCheck):
    code = "min-2-demos"
    category = Category.STRUCTURE
    stage = CheckStage.STRUCTURAL
    summary = "Every rung is demonstrated by at least two tasks."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        thin = [rung.name for rung in ctx.rungs if len(rung.demonstrations) < 2]
        yield self.finding(not thin, f"rungs with < 2 demonstrations: {thin}")


class TasksExist(LadderCheck):
    code = "tasks-exist"
    category = Category.STRUCTURE
    stage = CheckStage.CORPUS  # task ids are a fact about the GENERATED corpus
    summary = "Every demonstration and top task id resolves in the train corpus."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        missing = [
            demo.task_id
            for rung in ctx.rungs
            for demo in rung.demonstrations
            if demo.task_id not in ctx.by_id
        ]
        missing += [tid for tid in ctx.spec.top.task_ids if tid not in ctx.by_id]
        yield self.finding(not missing, f"unknown task ids in train_corpus: {missing}")


class MinTwoTrainExamples(LadderCheck):
    code = "min-2-train-examples"
    category = Category.STRUCTURE
    stage = CheckStage.CORPUS
    default_severity = "warn"
    summary = "Every demonstrating task shows at least two train examples."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        few = sorted(
            {
                tid
                for rung in ctx.rungs
                for demo in rung.demonstrations
                if (tid := demo.task_id) in ctx.by_id and len(ctx.by_id[tid].task.train) < 2
            }
        )
        yield self.finding(not few, f"tasks with < 2 train examples: {few}")


class RungReferenced(LadderCheck):
    """No dead rung.

    References point only downward (a rung elaborates over ``L_{i-1}``, enforced at load), so a
    rung is reachable from the top iff some HIGHER rung or top solution calls it. This is the
    DAG-general form of the old chain-only "the next rung calls it"; ``is_chain`` separately
    records whether the edges happen to form the simple spine -- reported, never required.
    """

    code = "rung-referenced"
    category = Category.STRUCTURE
    stage = CheckStage.STRUCTURAL
    summary = "Every rung is reachable from the top (some higher rung or top solution calls it)."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        for rung in ctx.rungs:
            yield self.finding(
                len(ctx.consumers[rung.name]) >= 1,
                f"no higher rung or top solution calls {rung.name}: it is dead "
                "(unreachable from the top at any depth_limit)",
                subject=rung.name,
            )


class RungDistinct(LadderCheck):
    """Two rungs with identical unfolded templates are one rung with two names: the second buys no
    depth and splits its own demonstrations. (Syntactic: extensionally-equal-but-differently-written
    twins pass.)"""

    code = "rung-distinct"
    category = Category.STRUCTURE
    stage = CheckStage.STRUCTURAL
    summary = "No two rungs unfold to the same floor-level template."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        unfolded = ctx.unfolded_templates
        for index, rung in enumerate(ctx.rungs):
            twin = next(
                (ctx.rungs[j].name for j in range(index) if unfolded[j] == unfolded[index]), None
            )
            yield self.finding(
                twin is None, f"identical unfolded template to {twin!r}", subject=rung.name
            )
