"""Resolve a lint finding to the source span it should squiggle.

A :class:`~...shape.LintFinding` names its subject in its ``check`` slug -- ``rung-referenced[rot180]``,
``constant-subterm[task-3]``, ``free-param-varies[shift#1]``. :class:`AnchorIndex` holds the exact
spans of every rung/task/floor entry (from the parsed document, C2) keyed by that same identifier, so
a finding maps to a precise range by lookup -- never by searching source text. A slug with no subject
(``levels-contiguous``) anchors to the ladder header.

This lives in the adapter layer: the lint machinery is untouched. When the checks become
``LadderCheck`` classes they will carry their own anchors and this becomes their shared helper.
"""

from __future__ import annotations

from dataclasses import dataclass

from arc_lab.program_search.ladders.diagnostics import Position, Range
from arc_lab.program_search.ladders.lang.parse import LadderDocument

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

    def resolve(self, slug: str) -> Range:
        """The span a finding with this ``check`` slug should anchor to."""
        opener = slug.find("[")
        if opener == -1:
            return self.file  # a file-level check (no named subject)
        occurrence = slug[opener + 1 : slug.rfind("]")]
        # Slugs carry `name`, `name#index`, or `name#l,#r`; the leading identifier is the subject.
        identifier = occurrence.split("#", 1)[0].split(",", 1)[0].strip()
        return (
            self.rungs.get(identifier)
            or self.tasks.get(identifier)
            or self.floor.get(identifier)
            or self.file
        )
