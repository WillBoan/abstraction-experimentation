"""AnchorIndex: a lint finding's subject resolves to that entity's exact source span."""

from __future__ import annotations

from arc_lab.program_search.ladders.anchors import AnchorIndex
from arc_lab.program_search.ladders.lang.parse import parse_document
from arc_lab.program_search.ladders.registry import ladder_paths
from arc_lab.program_search.ladders.shape import Occurrence


def _text_at(source: str, span: object) -> str:
    from arc_lab.program_search.ladders.diagnostics import Range

    assert isinstance(span, Range)
    line = source.splitlines()[span.start.line]
    return line[span.start.character : span.end.character]


def test_an_occurrence_resolves_to_its_subject_span() -> None:
    source = ladder_paths()["al1-mirror"].read_text()
    document = parse_document(source)
    index = AnchorIndex.from_document(document)

    rung = document.rungs[0].name
    task = document.rungs[0].tasks[0].task_id
    primitive = document.floor[0].name

    # A rung subject resolves to the exact rung name token -- params narrow the finding, not the
    # lookup, so a `#index` occurrence still anchors at the rung (C3 adds per-parameter spans).
    assert _text_at(source, index.resolve(Occurrence(rung))) == rung
    assert _text_at(source, index.resolve(Occurrence(rung, (1,)))) == rung
    assert _text_at(source, index.resolve(Occurrence(rung, (1, 2)))) == rung
    # Task and floor subjects resolve to that entity's span.
    assert index.resolve(Occurrence(task)) == index.tasks[task]
    assert index.resolve(Occurrence(primitive)) == index.floor[primitive]

    # No subject anchors to the ladder header; an unknown subject falls back to it too.
    assert index.resolve(None) == document.header_span
    assert index.resolve(Occurrence("nope")) == document.header_span


def test_from_document_covers_every_named_entity() -> None:
    for path in ladder_paths().values():
        document = parse_document(path.read_text())
        index = AnchorIndex.from_document(document)
        assert set(index.rungs) == {rung.name for rung in document.rungs}
        assert set(index.tasks) == {task.task_id for task in document.tasks()}
        assert set(index.floor) == {entry.name for entry in document.floor}
