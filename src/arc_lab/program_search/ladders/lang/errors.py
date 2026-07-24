"""The one load-time failure for `.ladder` sources (LADDER-FORMAT.md VAL-1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arc_lab.program_search.ladders.diagnostics import Range


class LadderFormatError(ValueError):
    """A `.ladder` source violates the format spec.

    ``detail`` is the message without location; ``line`` (1-based) is attached by whichever layer
    knows it -- the expression/type parsers work on fragments and leave it ``None``, the file
    parser adds it via :func:`at_line`. ``span`` is the precise source range when a layer can supply
    one (an elaboration error mapped through a fragment's source map); it drives editor squiggles
    while ``line`` drives CLI text.
    """

    def __init__(self, detail: str, *, line: int | None = None, span: Range | None = None) -> None:
        self.detail = detail
        self.line = line
        self.span = span
        super().__init__(detail if line is None else f"line {line}: {detail}")


class FragmentError(LadderFormatError):
    """An error at a known offset range *within* an elaboration fragment (a rung body or a task
    solution). ``start``/``end`` are code-point offsets into the fragment text; the caller that owns
    the fragment's source map turns them into a file :class:`~...diagnostics.Range`.
    """

    def __init__(self, detail: str, start: int, end: int) -> None:
        super().__init__(detail)
        self.start = start
        self.end = end


def at_line(error: LadderFormatError, line: int) -> LadderFormatError:
    """``error`` with ``line`` attached, unless it already carries a (more precise) location."""
    if error.line is not None:
        return error
    return LadderFormatError(error.detail, line=line, span=error.span)
