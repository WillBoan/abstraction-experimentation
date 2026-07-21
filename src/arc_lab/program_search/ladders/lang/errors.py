"""The one load-time failure for `.ladder` sources (LADDER-FORMAT.md VAL-1)."""

from __future__ import annotations


class LadderFormatError(ValueError):
    """A `.ladder` source violates the format spec.

    ``detail`` is the message without location; ``line`` (1-based) is attached by whichever layer
    knows it -- the expression/type parsers work on fragments and leave it ``None``, the file
    parser adds it via :func:`at_line`.
    """

    def __init__(self, detail: str, *, line: int | None = None) -> None:
        self.detail = detail
        self.line = line
        super().__init__(detail if line is None else f"line {line}: {detail}")


def at_line(error: LadderFormatError, line: int) -> LadderFormatError:
    """``error`` with ``line`` attached, unless it already carries a (more precise) location."""
    if error.line is not None:
        return error
    return LadderFormatError(error.detail, line=line)
