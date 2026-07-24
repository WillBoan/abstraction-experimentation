"""The lexer source map: every segment maps to the exact physical slice it came from."""

from __future__ import annotations

from arc_lab.program_search.ladders.diagnostics import Position, Range
from arc_lab.program_search.ladders.lang.parse import parse_document
from arc_lab.program_search.ladders.lang.source import scan_source
from arc_lab.program_search.ladders.registry import ladder_paths


def _text_at(source: str, span: Range) -> str:
    """The source substring under a (possibly multi-line) half-open range."""
    lines = source.splitlines()
    if span.start.line == span.end.line:
        return lines[span.start.line][span.start.character : span.end.character]
    parts = [lines[span.start.line][span.start.character :]]
    parts += lines[span.start.line + 1 : span.end.line]
    parts.append(lines[span.end.line][: span.end.character])
    return "\n".join(parts)


def test_every_registry_ladder_maps_segments_to_their_source() -> None:
    # For every committed ladder, each segment's joined-text slice must equal the physical slice it
    # claims to come from -- and its endpoints must round-trip through position().
    for name, path in ladder_paths().items():
        source = path.read_text()
        physical = source.splitlines()
        for statement in scan_source(source):
            for segment in statement.map.segments:
                claimed = statement.text[
                    segment.logical_start : segment.logical_start + segment.length
                ]
                actual = physical[segment.line][segment.column : segment.column + segment.length]
                assert claimed == actual, f"{name}: {segment} maps {claimed!r} != source {actual!r}"
                assert statement.map.position(segment.logical_start) == Position(
                    segment.line, segment.column
                )


def test_bracket_continuation_maps_across_physical_lines() -> None:
    source = "config {\n  x: [1,\n     2]\n}\n"
    statements = scan_source(source)
    texts = [s.text for s in statements]
    assert texts == ["config {", "x: [1, 2]", "}"]

    joined = statements[1]  # the continued statement
    assert joined.text == "x: [1, 2]"
    # Two segments, from physical lines 1 and 2 (0-based).
    assert [(seg.line, seg.column) for seg in joined.map.segments] == [(1, 2), (2, 5)]
    # The `2` lives at joined offset 7 -> physical line 2, column 5.
    assert joined.text[7] == "2"
    assert joined.map.position(7) == Position(2, 5)
    # The `[` is on the first physical line.
    assert joined.text[3] == "["
    assert joined.map.position(3) == Position(1, 5)


def test_range_spans_a_token_within_one_line() -> None:
    source = "floor lib {\n    use flip_h: (Grid) -> Grid\n}\n"
    use_line = scan_source(source)[1]
    assert use_line.text == "use flip_h: (Grid) -> Grid"
    start = use_line.text.index("flip_h")
    span = use_line.map.range(start, start + len("flip_h"))
    # `flip_h` starts at column 8 on physical line 1 (0-based): 4 spaces + "use ".
    assert span == Range(Position(1, 8), Position(1, 14))


def test_comment_and_leading_whitespace_do_not_shift_columns() -> None:
    source = "config {\n    depth: 2   # a trailing comment\n}\n"
    statement = scan_source(source)[1]
    assert statement.text == "depth: 2"
    # Column 4 = the four leading spaces; the comment tail is gone but never shifts what precedes it.
    assert statement.map.position(0) == Position(1, 4)
    assert statement.map.position(len("depth: 2")) == Position(1, 12)


def test_model_spans_point_at_their_source_tokens() -> None:
    # Across every committed ladder: each single-token span extracts exactly the token it names, and
    # solution/grid spans start at the right character. This is what lets Phase F anchor findings.
    for name, path in ladder_paths().items():
        source = path.read_text()
        document = parse_document(source)
        assert _text_at(source, document.name_span) == document.name, name

        for entry in document.floor:
            assert _text_at(source, entry.name_span) == entry.name, (name, entry.name)
        for config in document.config:
            assert _text_at(source, config.path_span) == config.path, (name, config.path)
        for rung in document.rungs:
            assert _text_at(source, rung.name_span) == rung.name, (name, rung.name)
        for block in document.distractors:
            assert _text_at(source, block.label_span) == block.label, (name, block.label)

        for task in document.tasks():
            assert _text_at(source, task.id_span) == task.task_id, (name, task.task_id)
            # The solution may be continuation-joined; check its first character lands correctly.
            first = source.splitlines()[task.solution_span.start.line][
                task.solution_span.start.character
            ]
            assert first == task.solution[0], (name, task.task_id, first, task.solution[0])
            if task.solution_span.start.line == task.solution_span.end.line:
                assert _text_at(source, task.solution_span) == task.solution, (name, task.task_id)
