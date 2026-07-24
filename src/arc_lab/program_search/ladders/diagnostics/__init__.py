"""Diagnostic value types for the `.ladder` toolchain -- the shared vocabulary of positions,
severities, and the one :class:`LadderDiagnostic` record every producer emits.

This package deliberately imports nothing from ``lang``/``checks``/``lsp``: it is the base layer
everything else depends on, never the reverse.
"""

from __future__ import annotations

from .diagnostic import LadderDiagnostic, Related, Severity, severity_from_legacy
from .positions import Position, Range

__all__ = [
    "LadderDiagnostic",
    "Position",
    "Range",
    "Related",
    "Severity",
    "severity_from_legacy",
]
