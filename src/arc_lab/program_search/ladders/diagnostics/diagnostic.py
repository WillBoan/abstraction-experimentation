"""``LadderDiagnostic``: the one shared value type every producer emits and every adapter renders.

There is exactly one such class. Variety lives in the ``code`` field, never in a per-kind subclass
hierarchy (that is the rejected anti-pattern). It maps 1:1 onto an LSP ``Diagnostic`` -- the CLI, the
language server, and the tests all consume this same value.

This is the deliberately-lean Phase-A/B core; later phases add fields (``category`` etc. looked up by
``code`` in a descriptor registry) additively, never changing the type's identity.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from .positions import Range


class Severity(enum.IntEnum):
    """Diagnostic severity. Integer values match LSP ``DiagnosticSeverity`` (1..4)."""

    ERROR = 1
    WARNING = 2
    INFORMATION = 3
    HINT = 4


#: The legacy ``LintFinding.severity`` strings, mapped onto :class:`Severity`.
_LEGACY_SEVERITY = {"error": Severity.ERROR, "warn": Severity.WARNING}


def severity_from_legacy(name: str) -> Severity:
    """Map a legacy ``"error"``/``"warn"`` string to a :class:`Severity` (unknown -> ERROR)."""
    return _LEGACY_SEVERITY.get(name, Severity.ERROR)


@dataclass(frozen=True, slots=True)
class Related:
    """A related source location + note. Same-document; the URI is injected at the LSP boundary."""

    range: Range
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class LadderDiagnostic:
    """One diagnostic: a stable ``code``, a source ``range``, a ``severity``, and a ``message``.

    ``occurrence`` is the parameterising identifier (a rung name, a task id) that the legacy lint
    slug carried in brackets; :attr:`slug` reconstructs the ``code[occurrence]`` display form.
    """

    code: str
    range: Range
    severity: Severity
    message: str
    source: str = "ladder"
    occurrence: str | None = None
    related: tuple[Related, ...] = ()

    @property
    def slug(self) -> str:
        """Legacy display form: ``code`` or ``code[occurrence]``."""
        return self.code if self.occurrence is None else f"{self.code}[{self.occurrence}]"
