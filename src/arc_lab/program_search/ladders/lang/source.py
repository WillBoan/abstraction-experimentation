"""The lexer's first pass: physical source -> logical statements, each carrying a source map.

Replaces the old ``(text, start_line)`` tuples. A logical statement is the comment-stripped,
bracket-continuation-joined text the block/section parsers consume -- plus a :class:`SourceMap` that
maps any offset in that joined text back to a physical ``(line, column)``. That map is what lets a
later diagnostic anchored inside a statement (a bad token, a type error in an expression) point at the
exact source span rather than the whole line.

Key facts that keep the map simple (see LADDER-FORMAT.md LEX):

- Comment removal (``#`` to end of line, quote-aware) only truncates a line's tail, and the per-line
  ``.strip()`` only trims its ends, so **each physical line contributes exactly one contiguous run**
  (:class:`Segment`) to the joined text -- never a reshuffle.
- Consecutive runs are joined by a single space; that space is synthetic (no source character).

The joined text is byte-identical to the old ``_logical_lines`` output, so the parsers and every
committed testbed are unaffected.
"""

from __future__ import annotations

from dataclasses import dataclass

from arc_lab.program_search.ladders.diagnostics import Position, Range
from arc_lab.program_search.ladders.lang.errors import LadderFormatError


@dataclass(frozen=True, slots=True)
class Segment:
    """One physical line's contiguous contribution to a logical statement's joined text."""

    #: Offset into the joined statement text where this run begins.
    logical_start: int
    #: Number of characters in the run.
    length: int
    #: 0-based physical line the run came from.
    line: int
    #: 0-based physical column where the run begins (past the stripped leading whitespace).
    column: int


@dataclass(frozen=True, slots=True)
class SourceMap:
    """Maps offsets in a logical statement's joined text back to physical positions."""

    segments: tuple[Segment, ...]

    def position(self, offset: int) -> Position:
        """The physical position of ``offset`` in the joined text.

        An offset inside a segment maps through it directly; one that lands on a synthetic join
        space (or at the very end) is attributed to the end of the preceding segment.
        """
        segments = self.segments
        if not segments:
            return Position(0, 0)
        offset = max(0, offset)
        for segment in segments:
            if segment.logical_start <= offset < segment.logical_start + segment.length:
                return Position(segment.line, segment.column + offset - segment.logical_start)
        # A boundary / join space / end offset: attribute to the last segment starting at or before it.
        chosen = segments[0]
        for segment in segments:
            if segment.logical_start <= offset:
                chosen = segment
        within = min(offset - chosen.logical_start, chosen.length)
        return Position(chosen.line, chosen.column + within)

    def range(self, start: int, end: int) -> Range:
        """The half-open physical range covering joined offsets ``[start, end)``."""
        return Range(self.position(start), self.position(end))


@dataclass(frozen=True, slots=True)
class Statement:
    """One logical statement: its joined text, the map back to source, and its full physical range."""

    text: str
    map: SourceMap
    range: Range


def scan_source(text: str) -> list[Statement]:
    """Split ``text`` into logical statements (comments stripped, bracket continuations joined)."""
    statements: list[Statement] = []
    segments: list[Segment] = []
    parts: list[str] = []
    logical_len = 0
    depth = 0
    for number, raw in enumerate(text.splitlines()):  # 0-based physical line
        stripped, lead, delta = _scan(raw)
        if not stripped and not parts:
            continue
        if stripped:
            if parts:
                logical_len += 1  # the single join space between runs
            segments.append(Segment(logical_len, len(stripped), number, lead))
            parts.append(stripped)
            logical_len += len(stripped)
        depth += delta
        if depth <= 0:
            if parts:
                source_map = SourceMap(tuple(segments))
                joined = " ".join(parts)
                statements.append(Statement(joined, source_map, source_map.range(0, len(joined))))
            segments, parts, logical_len, depth = [], [], 0, 0
    if parts:
        raise LadderFormatError("unbalanced `(` or `[` at end of file", line=segments[0].line + 1)
    return statements


def _scan(raw: str) -> tuple[str, int, int]:
    """One physical line -> ``(stripped, leading_columns, net (/[ depth change)``.

    Quotes are respected, so a ``#`` or a bracket inside a string value stays literal (spec LEX-2).
    ``leading_columns`` is the count of stripped leading whitespace -- the physical column at which
    the returned text begins.
    """
    out: list[str] = []
    depth = 0
    quote: str | None = None
    index = 0
    while index < len(raw):
        char = raw[index]
        if quote is not None:
            out.append(char)
            if char == "\\" and index + 1 < len(raw):
                out.append(raw[index + 1])
                index += 2
                continue
            if char == quote:
                quote = None
        elif char == "#":  # spec LEX-2
            break
        elif char in "\"'":
            quote = char
            out.append(char)
        else:
            if char in "([":
                depth += 1
            elif char in ")]":
                depth -= 1
            out.append(char)
        index += 1
    joined = "".join(out)
    lead = len(joined) - len(joined.lstrip())
    return joined.strip(), lead, depth
