"""Diagnostic value primitives: positions, half-open ranges, severity mapping, the slug form."""

from __future__ import annotations

import pytest

from arc_lab.program_search.ladders.diagnostics import (
    LadderDiagnostic,
    Position,
    Range,
    Severity,
    severity_from_legacy,
)


def test_severity_values_match_lsp() -> None:
    # The integer values must equal LSP DiagnosticSeverity so conversion is value-preserving.
    assert (Severity.ERROR, Severity.WARNING, Severity.INFORMATION, Severity.HINT) == (1, 2, 3, 4)


def test_positions_order() -> None:
    assert Position(1, 0) < Position(1, 3) < Position(2, 0)


def test_range_is_half_open_and_validated() -> None:
    r = Range(Position(3, 2), Position(3, 7))
    assert r.human() == "4:3"  # 1-based line:col of the start
    with pytest.raises(ValueError, match="precedes start"):
        Range(Position(3, 7), Position(3, 2))


def test_severity_from_legacy() -> None:
    assert severity_from_legacy("error") is Severity.ERROR
    assert severity_from_legacy("warn") is Severity.WARNING
    assert severity_from_legacy("mystery") is Severity.ERROR  # unknown -> error


def test_slug_reconstructs_bracketed_occurrence() -> None:
    zero = Range(Position(0, 0), Position(0, 0))
    plain = LadderDiagnostic(code="min-2-demos", range=zero, severity=Severity.ERROR, message="x")
    param = LadderDiagnostic(
        code="rung-referenced",
        range=zero,
        severity=Severity.ERROR,
        message="x",
        occurrence="rot180",
    )
    assert plain.slug == "min-2-demos"
    assert param.slug == "rung-referenced[rot180]"
