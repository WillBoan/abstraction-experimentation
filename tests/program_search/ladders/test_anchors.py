"""AnchorIndex: a lint finding's slug resolves to the exact source span of its subject."""

from __future__ import annotations

from arc_lab.program_search.ladders.anchors import AnchorIndex
from arc_lab.program_search.ladders.lang.parse import parse_document
from arc_lab.program_search.ladders.registry import ladder_paths


def _text_at(source: str, span: object) -> str:
    from arc_lab.program_search.ladders.diagnostics import Range

    assert isinstance(span, Range)
    line = source.splitlines()[span.start.line]
    return line[span.start.character : span.end.character]


def test_slug_resolves_to_its_subject_span() -> None:
    source = ladder_paths()["al1-mirror"].read_text()
    document = parse_document(source)
    index = AnchorIndex.from_document(document)

    rung = document.rungs[0].name
    task = document.rungs[0].tasks[0].task_id
    primitive = document.floor[0].name

    # A rung slug resolves to the exact rung name token, including a `#index` param suffix.
    assert _text_at(source, index.resolve(f"rung-referenced[{rung}]")) == rung
    assert _text_at(source, index.resolve(f"jump-affordable[{rung}]")) == rung
    assert _text_at(source, index.resolve(f"free-param-varies[{rung}#0]")) == rung
    # Task and floor slugs resolve to that entity's span.
    assert index.resolve(f"constant-subterm[{task}]") == index.tasks[task]
    assert index.resolve(f"hof-holes-fillable[{primitive}]") == index.floor[primitive]

    # A file-level slug (no subject) anchors to the ladder header; an unknown subject falls back too.
    assert index.resolve("levels-contiguous") == document.header_span
    assert index.resolve("mystery[nope]") == document.header_span


def test_from_document_covers_every_named_entity() -> None:
    for path in ladder_paths().values():
        document = parse_document(path.read_text())
        index = AnchorIndex.from_document(document)
        assert set(index.rungs) == {rung.name for rung in document.rungs}
        assert set(index.tasks) == {task.task_id for task in document.tasks()}
        assert set(index.floor) == {entry.name for entry in document.floor}
