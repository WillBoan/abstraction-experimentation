"""Markdown helpers shared by the two generated-artifact renderers (``spec.md`` / ``results.md``).

The generated files are exempted from editor auto-formatting (root ``.prettierignore``), so the
emitters own their final byte form; ``table`` pads columns the way Prettier formats narrow tables,
keeping the output readable in any viewer.
"""

from __future__ import annotations

from collections.abc import Sequence


def table(rows: Sequence[Sequence[str]]) -> list[str]:
    """Aligned markdown table lines: ``rows[0]`` is the header; cells are left-justified to the
    column width (minimum 3, so the separator dashes always form a valid delimiter row)."""
    widths = [max(3, *(len(row[column]) for row in rows)) for column in range(len(rows[0]))]

    def fmt(row: Sequence[str]) -> str:
        cells = (cell.ljust(width) for cell, width in zip(row, widths, strict=True))
        return "| " + " | ".join(cells) + " |"

    separator = "| " + " | ".join("-" * width for width in widths) + " |"
    return [fmt(rows[0]), separator, *(fmt(row) for row in rows[1:])]
