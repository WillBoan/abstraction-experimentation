"""Resolve a lint finding to the source span it should squiggle.

A :class:`~.shape.LintFinding` names its subject structurally -- an :class:`~.shape.Occurrence`
carrying a rung name, a task id or a floor primitive. :class:`AnchorIndex` holds the exact spans of
those entities (from the parsed document, C2) keyed by that same identifier, so a finding maps to a
precise range by **lookup**: never by searching the source text, and never by taking a slug string
apart. A finding with no subject (``levels-contiguous``) anchors to the ladder header.
"""

from __future__ import annotations

from dataclasses import dataclass

from arc_lab.program_search.ladders.diagnostics import Position, Range
from arc_lab.program_search.ladders.lang.parse import LadderDocument
from arc_lab.program_search.ladders.shape import Occurrence

_FILE_FALLBACK = Range(Position(0, 0), Position(0, 0))


@dataclass(frozen=True, slots=True)
class AnchorIndex:
    """Exact source spans of a document's named entities, plus a whole-file fallback."""

    rungs: dict[str, Range]
    tasks: dict[str, Range]
    floor: dict[str, Range]
    file: Range

    @classmethod
    def from_document(cls, document: LadderDocument) -> AnchorIndex:
        return cls(
            rungs={rung.name: rung.name_span for rung in document.rungs},
            tasks={task.task_id: task.header_span for task in document.tasks()},
            floor={entry.name: entry.name_span for entry in document.floor},
            file=document.header_span or _FILE_FALLBACK,
        )

    def resolve(self, occurrence: Occurrence | None) -> Range:
        """The span a finding about this occurrence should anchor to.

        The subject is looked up in each namespace in turn -- rung, task, floor entry -- and falls
        back to the ladder header when it names nothing the document declares (a programmatic spec,
        or an entity this parse never saw). ``occurrence.params`` is not consulted yet: narrowing a
        free-parameter finding to the parameter's own span needs per-parameter spans on the parsed
        rung header, which C3 adds.
        """
        if occurrence is None:
            return self.file
        return (
            self.rungs.get(occurrence.subject)
            or self.tasks.get(occurrence.subject)
            or self.floor.get(occurrence.subject)
            or self.file
        )
