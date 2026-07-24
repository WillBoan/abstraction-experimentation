"""The shared `.ladder` diagnostics pipeline: source text -> :class:`LadderDiagnostic`\\ s.

The one producer both adapters call -- the language server (``lsp/server.py``) and the CLI
(``cli/lint_ladder.py`` ``--json``) are siblings over :func:`lint_source`, so a diagnostic is
computed once and rendered two ways (LSP wire, or the CLI's domain JSON / text).

Still over the CURRENT strict pipeline (parse -> resolve -> lint): a parse/resolve failure yields one
diagnostic (precise when the error carries a span, else the whole line); a successful load runs the
lint and anchors each finding through the :class:`AnchorIndex`. The tolerant parser (Phase D) will
change *how many* diagnostics come back and *whether the document is partial* -- never this signature.

**Two tiers, forced by a measured fact:** on al14 the full lint takes ~4.6s (dominated by the
*structural* unfold-based depth checks -- ``corpus_backed=False`` is no faster), while parse+resolve
is ~2ms. So :func:`lint_source` gates the lint behind ``run_lint``: the server runs the cheap tier on
every change and the full tier on open/save.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from .diagnostics import LadderDiagnostic, Position, Range, Severity, severity_from_legacy
from .shape import LintFinding

if TYPE_CHECKING:
    from .anchors import AnchorIndex
    from .lang.errors import LadderFormatError


def lint_source(source: str, *, run_lint: bool = True) -> list[LadderDiagnostic]:
    """Diagnose one `.ladder` document's text. Never raises for a well-formed load failure.

    ``run_lint=False`` runs only the ~2ms parse+resolve tier (syntax / type / resolution errors);
    ``run_lint=True`` adds the full lint (seconds on a deep ladder).
    """
    from .anchors import AnchorIndex
    from .lang.errors import LadderFormatError
    from .lang.load import lintable_spec, resolve
    from .lang.parse import parse_document

    lines = source.splitlines()
    try:
        loaded = resolve(parse_document(source))
    except LadderFormatError as exc:
        return [_from_format_error(exc, lines)]

    # A draft cannot run the corpus lint -- either because its floor is assumed (nothing to
    # evaluate) or because it has no train/heldout corpus to evaluate against. The two are
    # independent; stay quiet for both rather than half-reporting, and never raise (an editor calls
    # this on every keystroke). `arc-lab lint-ladder --draft` reports the structural tier instead.
    if not run_lint or loaded.assumed:
        return []
    spec = lintable_spec(loaded)
    if spec is None:
        return []

    anchors = AnchorIndex.from_document(loaded.document)
    return [_from_finding(finding, anchors) for finding in spec.lint().findings if not finding.ok]


def diagnostics_to_json(diagnostics: Sequence[LadderDiagnostic], *, path: str) -> dict[str, object]:
    """One target's diagnostics as the CLI's domain JSON (a superset of the LSP wire shape)."""
    has_error = any(d.severity is Severity.ERROR for d in diagnostics)
    return {
        "path": path,
        "outcome": "failed" if has_error else "clean",
        "diagnostics": [_diagnostic_to_json(d) for d in diagnostics],
    }


def _diagnostic_to_json(diagnostic: LadderDiagnostic) -> dict[str, object]:
    entry: dict[str, object] = {
        "code": diagnostic.code,
        "severity": diagnostic.severity.name.lower(),
        "message": diagnostic.message,
        "range": {
            "start": {
                "line": diagnostic.range.start.line,
                "character": diagnostic.range.start.character,
            },
            "end": {"line": diagnostic.range.end.line, "character": diagnostic.range.end.character},
        },
    }
    if diagnostic.occurrence is not None:
        entry["occurrence"] = diagnostic.occurrence
    return entry


def _from_format_error(exc: LadderFormatError, lines: Sequence[str]) -> LadderDiagnostic:
    # A precise span (an elaboration error mapped through its fragment's source map) wins; otherwise
    # fall back to the whole offending line.
    if exc.span is not None:
        source_range = exc.span
    else:
        line0 = exc.line - 1 if exc.line is not None else 0
        source_range = _line_range(lines, line0)
    return LadderDiagnostic(
        code="load-error", range=source_range, severity=Severity.ERROR, message=exc.detail
    )


def _from_finding(finding: LintFinding, anchors: AnchorIndex) -> LadderDiagnostic:
    # The finding names its subject structurally, so the AnchorIndex resolves it to the exact source
    # span (rung / task / floor entry) by lookup -- the code stays the bare, stable check code.
    return LadderDiagnostic(
        code=finding.code,
        range=anchors.resolve(finding.occurrence),
        severity=severity_from_legacy(finding.severity),
        message=finding.detail,
        occurrence=None if finding.occurrence is None else str(finding.occurrence),
    )


def _line_range(lines: Sequence[str], line0: int) -> Range:
    """The whole of physical line ``line0`` (0-based) as a half-open range; empty at file start
    when the line is out of bounds (a positionless finding)."""
    if 0 <= line0 < len(lines):
        return Range(Position(line0, 0), Position(line0, len(lines[line0])))
    return Range(Position(0, 0), Position(0, 0))
