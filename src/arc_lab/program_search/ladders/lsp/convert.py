"""Convert :class:`LadderDiagnostic` (our value type) to an ``lsprotocol`` ``Diagnostic``.

The single boundary where the domain diagnostic meets the wire protocol. Keeping it here means the
rest of the toolchain never imports ``lsprotocol``.
"""

from __future__ import annotations

from lsprotocol import types as lsp

from ..diagnostics import LadderDiagnostic, Position, Range


def _position(position: Position) -> lsp.Position:
    # Internal positions are already non-negative; the floor is belt-and-suspenders at the boundary.
    return lsp.Position(line=max(0, position.line), character=max(0, position.character))


def _range(source_range: Range) -> lsp.Range:
    return lsp.Range(start=_position(source_range.start), end=_position(source_range.end))


def to_lsp(diagnostic: LadderDiagnostic, *, uri: str) -> lsp.Diagnostic:
    """Render one diagnostic for publication against ``uri``."""
    related = [
        lsp.DiagnosticRelatedInformation(
            location=lsp.Location(uri=uri, range=_range(rel.range)),
            message=rel.message,
        )
        for rel in diagnostic.related
    ]
    return lsp.Diagnostic(
        range=_range(diagnostic.range),
        message=diagnostic.message,
        severity=lsp.DiagnosticSeverity(diagnostic.severity.value),
        # Shim: the slug carries the occurrence inline. Phase G switches to the bare `code` with the
        # occurrence in `Diagnostic.data`.
        code=diagnostic.slug,
        source=diagnostic.source,
        related_information=related or None,
    )
