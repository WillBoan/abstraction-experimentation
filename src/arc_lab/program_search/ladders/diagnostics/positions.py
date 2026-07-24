"""Source positions and ranges: the coordinate types every diagnostic anchors to.

Conventions, held everywhere internal (see AL-PLAN-LADDER-EDITOR-TOOLING-2026-07-23.md):

- **0-based**, LSP-native. Human/CLI text adds one (:meth:`Range.human`).
- Columns are **code points**. LEX-1 mandates ASCII source, so for every valid `.ladder`
  file a code-point column equals its UTF-16 unit and the conversion at the LSP boundary is
  the identity; the converter clamps defensively for the invalid (mid-edit, non-ASCII) buffers
  a live server is inevitably handed.
- Ranges are **half-open** ``[start, end)`` with ``start <= end``.

These are pure value types -- no source-text coupling, no protocol types. The LSP mapping lives
in ``ladders/lsp/convert.py``; a future ``SourceText`` (Phase B) will own text<->offset math.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, order=True)
class Position:
    """A 0-based ``(line, character)`` source position; ``character`` counts code points."""

    line: int
    character: int


@dataclass(frozen=True, slots=True)
class Range:
    """A half-open ``[start, end)`` source range."""

    start: Position
    end: Position

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"range end {self.end} precedes start {self.start}")

    def human(self) -> str:
        """1-based ``line:col`` of the start, for CLI text."""
        return f"{self.start.line + 1}:{self.start.character + 1}"
