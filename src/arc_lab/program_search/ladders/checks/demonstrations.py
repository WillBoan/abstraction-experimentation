"""Demonstration plan (P): what the TASKS themselves show.

These used to hold by construction -- ``taskgen``'s seed generator built varied grids and
``RungTasks.train_args`` built the free-parameter sweep -- but a `.ladder` file states both as
literal data, so nothing enforces them any more except these checks.

Two sub-families. The *grid* checks ask whether each task is a real task (distinct inputs, varying
outputs, not the identity, heldout genuinely held out). The *variation* checks ask whether the
demonstrations generalise: a rung's free parameters must be shown at more than one value, and no
two of them may move in lockstep. The *collapse* checks (constancy, conditionals) evaluate the
stated solutions' subterms and are the static form of the al14 literal-collapse diagnosis.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from itertools import combinations

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.program_search.ladders.checks.base import Category, CheckStage, LadderCheck
from arc_lab.program_search.ladders.checks.context import CheckContext
from arc_lab.program_search.ladders.checks.evaluation import (
    conditional_verdicts,
    constancy_verdicts,
)
from arc_lab.program_search.ladders.shape import LintFinding
from arc_lab.program_search.ladders.spec import Demonstration, DemonstrationKind
from arc_lab.program_search.substrate.program import Apply, Input


class DistinctTrainInputs(LadderCheck):
    code = "distinct-train-inputs"
    category = Category.DEMONSTRATION
    stage = CheckStage.CORPUS
    summary = "No task repeats a train input."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        for entry in ctx.all_entries:
            inputs = [ex.input for ex in entry.task.train]
            yield self.finding(
                len(set(inputs)) == len(inputs),
                "repeated train inputs: the example set is smaller than it looks",
                occurrence=entry.task.task_id,
            )


class OutputsVary(LadderCheck):
    code = "outputs-vary"
    category = Category.DEMONSTRATION
    stage = CheckStage.CORPUS
    summary = "No task has a single repeated train output (a constant program would fit it)."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        for entry in ctx.all_entries:
            outputs = [ex.output for ex in entry.task.train]
            yield self.finding(
                len(set(outputs)) > 1 or len(outputs) < 2,
                "every train output is the same grid: a constant program fits the task",
                occurrence=entry.task.task_id,
            )


class NotIdentity(LadderCheck):
    code = "not-identity"
    category = Category.DEMONSTRATION
    stage = CheckStage.CORPUS
    summary = "No task is solved by the identity on every train example."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        for entry in ctx.all_entries:
            inputs = [ex.input for ex in entry.task.train]
            outputs = [ex.output for ex in entry.task.train]
            yield self.finding(
                any(a != b for a, b in zip(inputs, outputs, strict=True)),
                "output == input on every train example: the identity fits the task",
                occurrence=entry.task.task_id,
            )


class HeldoutDistinct(LadderCheck):
    """A heldout task must be a genuinely different task, or transfer is measured to itself."""

    code = "heldout-distinct"
    category = Category.DEMONSTRATION
    stage = CheckStage.CORPUS
    summary = "No heldout task duplicates a train task's examples."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        train_keys = {
            _task_key(entry): entry.task.task_id for entry in ctx.spec.train_corpus.entries
        }
        for entry in ctx.spec.heldout_corpus.entries:
            twin = train_keys.get(_task_key(entry))
            yield self.finding(
                twin is None,
                f"identical train examples to the train task {twin!r}",
                occurrence=entry.task.task_id,
            )


class FreeParamVaries(LadderCheck):
    """A rung's FREE parameters must be demonstrated at more than one value, or antiunification has
    nothing to generalise over and mints the specialised form.

    A ``fragment_identical`` rung is exempt: identical instantiation across its demos is that
    kind's definition -- what varies for it is the surrounding context.
    """

    code = "free-param-varies"
    category = Category.DEMONSTRATION
    stage = CheckStage.STRUCTURAL
    summary = "Every free rung parameter is demonstrated at more than one value."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        for rung in ctx.rungs:
            demos = _generalising_demos(rung.demonstrations)
            for free_index, values in rung_argument_columns(demos, rung.name):
                yield self.finding(
                    len(set(values)) > 1 or len(demos) < 2,
                    f"every demonstration passes {min(values, default='?')}: the mint "
                    "will specialise to it instead of taking a parameter",
                    occurrence=f"{rung.name}#{free_index}",
                )


class FreeParamsCovary(LadderCheck):
    """Antiunification gives ONE parameter to every position whose disagreement pair is the same,
    so two free positions holding identical values at every call site fuse into a single shared
    param.

    Measured 2026-07-23 (sleep-probes S-B): demos ``(2,2)`` and ``(5,5)`` for a 2-param rung mint
    arity 2 with a shared ``#1, #1``, not the intended arity 3. Both positions VARY, so
    ``free-param-varies`` passes clean -- this is the failure mode it cannot see.
    """

    code = "free-params-covary"
    category = Category.DEMONSTRATION
    stage = CheckStage.STRUCTURAL
    summary = "No two free rung parameters hold the same value at every call site."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        for rung in ctx.rungs:
            demos = _generalising_demos(rung.demonstrations)
            columns = rung_argument_columns(demos, rung.name)
            for (left, left_values), (right, right_values) in combinations(columns, 2):
                yield self.finding(
                    left_values != right_values or len(set(left_values)) < 2 or len(demos) < 2,
                    f"positions #{left} and #{right} hold the same value at every call site, so "
                    "antiunification shares ONE parameter between them: the mint fuses the two "
                    "and cannot express the case where they differ",
                    occurrence=f"{rung.name}#{left},#{right}",
                )


class ConstantSubterm(LadderCheck):
    """A composite subterm whose value is train-constant contributes no real depth: the enumerator
    keeps the cheapest representative of each behavioral class, so a literal beats it outright
    whenever that value is in the ladder's own configured constant domain.

    Severity is the law's "does the beating literal exist in THIS ladder's search?" clause: ERROR
    when it does, WARN (fictional depth) when the value is merely constant but not mintable here.
    """

    code = "constant-subterm"
    category = Category.DEMONSTRATION
    stage = CheckStage.CORPUS
    summary = "No stated solution contains a train-constant composite scalar subterm."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        sources = tuple(
            getattr(ctx.spec.reference_config.search_engine, "constant_sources", ()) or ()
        )
        yield from self.stamp(
            constancy_verdicts(ctx.unfolded_stated, ctx.train_inputs, ctx.full_lib, sources)
        )


class IfConditionVaries(LadderCheck):
    """The constancy law's branching corollary: an ``If`` whose condition is constant across a
    task's train examples has the taken branch's signature, so search keeps the branch alone and the
    conditional collapses."""

    code = "if-condition-varies"
    category = Category.DEMONSTRATION
    stage = CheckStage.CORPUS
    summary = "Every conditional's condition takes both truth values across a task's examples."

    def run(self, ctx: CheckContext) -> Iterator[LintFinding]:
        yield from self.stamp(
            conditional_verdicts(ctx.unfolded_stated, ctx.train_inputs, ctx.full_lib)
        )


def _generalising_demos(demonstrations: Sequence[Demonstration]) -> list[Demonstration]:
    """The demonstrations the variation checks read -- ``fragment_identical`` demos excluded."""
    return [d for d in demonstrations if d.kind is not DemonstrationKind.FRAGMENT_IDENTICAL]


def _task_key(entry: AnnotatedTask) -> tuple[tuple[object, object], ...]:
    """A task's train examples as a hashable key -- what makes two tasks the same task."""
    return tuple((example.input, example.output) for example in entry.task.train)


def rung_argument_columns(
    demos: Sequence[Demonstration], rung_name: str
) -> tuple[tuple[int, tuple[str, ...]], ...]:
    """Per free argument position of ``rung_name``: (1-based index, arguments observed IN ORDER).

    Aggregated over EVERY call site of EVERY demonstration -- each call is an occurrence the
    proposer sees, so a second call site with a different argument is variation. Arguments are
    compared column-wise, keeping call sites aligned even when one demo pipes a computed grid
    where another pipes ``input``; a column whose every observed argument is ``Input()`` is the
    piped grid, not a free parameter, and is dropped, with the survivors renumbered 1..n.

    Order is preserved (not a set) because two checks need different things from it:
    ``free-param-varies`` asks how many DISTINCT values a column holds, while
    ``free-params-covary`` asks whether two columns hold the same value *at the same call site* --
    which set equality cannot see (``[2, 5]`` and ``[5, 2]`` share a set but never covary).
    """
    calls = [
        node.args
        for demo in demos
        for node in demo.solution.walk()
        if isinstance(node, Apply) and node.primitive == rung_name
    ]
    columns: list[tuple[int, tuple[str, ...]]] = []
    free_index = 0
    for position in range(max((len(args) for args in calls), default=0)):
        observed = [args[position] for args in calls if position < len(args)]
        if all(isinstance(arg, Input) for arg in observed):
            continue
        free_index += 1
        columns.append((free_index, tuple(str(arg) for arg in observed)))
    return tuple(columns)
