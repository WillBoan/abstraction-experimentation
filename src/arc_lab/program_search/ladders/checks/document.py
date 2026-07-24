"""Syntax (stage SYNTAX): pure predicates over the parsed document, before anything resolves.

Each of these asks a question the file answers on its own -- is anything declared twice, is the
floor empty -- so none of them needs the substrate, a library, or an elaborated template. That is
what makes them separable, and it is the whole test for belonging here.

Two consumers, one definition. The strict loader (``lang/load.py::resolve``) runs them first and
raises the first error, which is what it always did and where these rules used to live inline. The
editor runs them over the parsed document and reports **all** of them at once, each on its exact
span -- something the loader structurally cannot do, because it has to stop at the first one.

Most load-time errors do NOT belong here and are not moved: an unknown floor primitive, a
mistyped rung template, a bad config value are all raised *while constructing* the thing they
describe, so there is no completed model to run a predicate over. They become checks when the
tolerant resolver gives them one (plan Phase E2), not before.
"""

from __future__ import annotations

from collections.abc import Iterator

from arc_lab.program_search.ladders.checks.base import Category, DocumentCheck
from arc_lab.program_search.ladders.lang.parse import LadderDocument
from arc_lab.program_search.ladders.shape import LintFinding


class FloorNonEmpty(DocumentCheck):
    """Spec FLR-3: a floor with no primitives gives the ladder nothing to compose over."""

    code = "floor-non-empty"
    category = Category.STRUCTURE
    summary = "The floor declares at least one primitive (spec FLR-3)."

    def run(self, document: LadderDocument) -> Iterator[LintFinding]:
        if not document.floor:
            yield self.finding(False, "the floor needs at least one primitive (spec FLR-3)")


class FloorNamesUnique(DocumentCheck):
    """A floor primitive declared twice: the second `use` line is silently dead."""

    code = "floor-names-unique"
    category = Category.STRUCTURE
    summary = "No floor primitive is declared twice."

    def run(self, document: LadderDocument) -> Iterator[LintFinding]:
        seen: set[str] = set()
        for entry in document.floor:
            if entry.name in seen:
                yield self.finding(
                    False,
                    f"duplicate floor primitive {entry.name!r}",
                    subject=entry.name,
                    anchor=entry.name_span,
                )
            seen.add(entry.name)


class ConfigPathsUnique(DocumentCheck):
    """The same override stated twice: one of the two values is silently discarded."""

    code = "config-paths-unique"
    category = Category.STRUCTURE
    summary = "No config path is overridden twice."

    def run(self, document: LadderDocument) -> Iterator[LintFinding]:
        seen: set[str] = set()
        for entry in document.config:
            if entry.path in seen:
                yield self.finding(
                    False,
                    f"duplicate config path {entry.path!r}",
                    subject=entry.path,
                    anchor=entry.path_span,
                )
            seen.add(entry.path)


class TaskIdsUnique(DocumentCheck):
    """Task ids key the corpus, so a repeat would make one of the two tasks unreachable."""

    code = "task-ids-unique"
    category = Category.STRUCTURE
    summary = "No task id is used twice."

    def run(self, document: LadderDocument) -> Iterator[LintFinding]:
        seen: set[str] = set()
        for block in document.tasks():
            if block.task_id in seen:
                yield self.finding(
                    False,
                    f"duplicate task id {block.task_id!r}",
                    subject=block.task_id,
                    anchor=block.id_span,
                )
            seen.add(block.task_id)
