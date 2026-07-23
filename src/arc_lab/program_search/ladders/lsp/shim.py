"""Phase-A shim: produce diagnostics for a `.ladder` source via the CURRENT strict pipeline.

This is the temporary bridge that lets the language server ship before the tolerant parser and the
shared ``lint_source`` pipeline exist. It is deliberately pygls-free (only ``lang`` + ``diagnostics``)
so the diagnostic production is unit-testable without the editor stack.

Scope of the shim, and its known imprecision (all fixed by later phases, none of it load-bearing):

- The strict parser raises on the first error, so a parse/resolve failure yields **one** diagnostic
  spanning the whole offending line (from ``LadderFormatError.line``). Phase D makes it tolerant and
  precise.
- Lint findings carry no source anchor yet, so they land at line 0. Phase F anchors them.

**Two tiers, forced by a measured fact:** on al14 the full lint takes ~4.6s (dominated by the
*structural* unfold-based depth checks, not the corpus-backed ones -- ``corpus_backed=False`` is no
faster), while parse+resolve is ~2ms. So :func:`diagnose` gates the lint behind ``run_lint``: the
server runs the cheap parse+resolve tier on every change and the full tier on open/save. This is the
plan's tier policy in miniature (Phase H makes it async + debounced + generation-guarded).

What is already the real, forward-compatible machinery: the :class:`LadderDiagnostic` value type, the
tier seam, and routing the strict failure through a single conversion point. Phase G lifts
:func:`diagnose` into ``ladders/pipeline.py::lint_source`` and deletes this module.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ..diagnostics import LadderDiagnostic, Position, Range, Severity, severity_from_legacy
from ..shape import LintFinding

if TYPE_CHECKING:
    from ..anchors import AnchorIndex
    from ..lang.errors import LadderFormatError


def diagnose(source: str, *, run_lint: bool = True) -> list[LadderDiagnostic]:
    """Diagnose one `.ladder` document's text. Never raises for a well-formed load failure.

    ``run_lint=False`` runs only the ~2ms parse+resolve tier (syntax / type / resolution errors) --
    what the server runs per keystroke; ``run_lint=True`` adds the full lint (seconds on a deep
    ladder), run on open/save.
    """
    from ..lang.errors import LadderFormatError
    from ..lang.load import draft_spec, resolve
    from ..lang.parse import parse_document

    lines = source.splitlines()
    try:
        loaded = resolve(parse_document(source))
    except LadderFormatError as exc:
        return [_from_format_error(exc, lines)]

    # A draft over assumed primitives cannot run the corpus lint (nothing to evaluate); the shim
    # stays quiet rather than half-reporting. `arc-lab lint-ladder --draft` covers that case.
    if not run_lint or loaded.assumed:
        return []

    from ..anchors import AnchorIndex

    anchors = AnchorIndex.from_document(loaded.document)
    shape = draft_spec(loaded).lint()
    return [_from_finding(finding, anchors) for finding in shape.findings if not finding.ok]


def _from_format_error(exc: LadderFormatError, lines: Sequence[str]) -> LadderDiagnostic:
    # A precise span (an elaboration error mapped through its fragment's source map) wins; otherwise
    # fall back to the whole offending line.
    if exc.span is not None:
        source_range = exc.span
    else:
        line0 = exc.line - 1 if exc.line is not None else 0
        source_range = _line_range(lines, line0)
    return LadderDiagnostic(
        code="load-error",
        range=source_range,
        severity=Severity.ERROR,
        message=exc.detail,
    )


def _from_finding(finding: LintFinding, anchors: AnchorIndex) -> LadderDiagnostic:
    # `finding.check` is the legacy slug (may embed `[occurrence]`); the AnchorIndex maps it to the
    # exact source span of its subject (rung / task / floor entry), or the ladder header.
    return LadderDiagnostic(
        code=finding.check,
        range=anchors.resolve(finding.check),
        severity=severity_from_legacy(finding.severity),
        message=finding.detail,
    )


def _line_range(lines: Sequence[str], line0: int) -> Range:
    """The whole of physical line ``line0`` (0-based) as a half-open range; empty at file start
    when the line is out of bounds (a positionless finding)."""
    if 0 <= line0 < len(lines):
        return Range(Position(line0, 0), Position(line0, len(lines[line0])))
    return Range(Position(0, 0), Position(0, 0))
