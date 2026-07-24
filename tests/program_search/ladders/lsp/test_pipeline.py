"""The shared diagnostics pipeline: strict pipeline -> LadderDiagnostic, and the LSP conversion.

Also the latency baseline (parse+resolve+lint on the largest ladder) that informs the server's
debounce / tier policy -- recorded, with only a generous backstop assertion (no flaky tight bound).
"""

from __future__ import annotations

import time

from arc_lab.program_search.ladders.diagnostics import LadderDiagnostic, Position, Range, Severity
from arc_lab.program_search.ladders.lsp.convert import to_lsp
from arc_lab.program_search.ladders.pipeline import (
    _from_finding,
    _from_format_error,
    _line_range,
    lint_source,
)
from arc_lab.program_search.ladders.registry import ladder_paths
from arc_lab.program_search.ladders.shape import LintFinding

_CLEAN = "al1-mirror"  # the canonical clean reference ladder
_LARGEST = "al14-cell-row-grid"  # the deepest committed ladder -- the latency worst case


def test_clean_ladder_has_no_error_diagnostics() -> None:
    source = ladder_paths()[_CLEAN].read_text()
    diags = lint_source(source)
    assert not [d for d in diags if d.severity is Severity.ERROR], (
        f"the reference ladder should lint error-clean, got {[d.slug for d in diags]}"
    )


def test_parse_error_yields_one_line_level_load_error() -> None:
    diags = lint_source("this is not a ladder file\n")
    assert len(diags) == 1
    (only,) = diags
    assert only.code == "load-error"
    assert only.severity is Severity.ERROR
    assert only.range.start.line >= 0


def test_line_range_spans_the_whole_line() -> None:
    r = _line_range(["ab", "cde"], 1)
    assert r == Range(Position(1, 0), Position(1, 3))
    # Out-of-bounds (a positionless finding) collapses to the file start.
    assert _line_range((), 5) == Range(Position(0, 0), Position(0, 0))


def test_finding_becomes_a_diagnostic() -> None:
    from arc_lab.program_search.ladders.anchors import AnchorIndex

    header = Range(Position(0, 0), Position(0, 5))
    anchors = AnchorIndex(rungs={}, tasks={}, floor={}, file=header)
    finding = LintFinding(code="min-2-demos", ok=False, detail="rung r has 1 demo", severity="warn")
    diag = _from_finding(finding, anchors)
    assert diag.code == "min-2-demos"
    assert diag.severity is Severity.WARNING
    assert diag.message == "rung r has 1 demo"
    assert diag.range == header  # a subjectless finding anchors to the ladder header


def test_format_error_maps_line_and_detail() -> None:
    from arc_lab.program_search.ladders.lang.errors import LadderFormatError

    diag = _from_format_error(LadderFormatError("bad thing", line=2), ["one", "two", "three"])
    assert diag.code == "load-error"
    assert diag.message == "bad thing"
    assert diag.range == Range(Position(1, 0), Position(1, 3))  # line 2 (1-based) -> index 1


def test_conversion_to_lsp_preserves_severity_and_range() -> None:
    diag = LadderDiagnostic(
        code="rung-referenced",
        range=Range(Position(4, 2), Position(4, 9)),
        severity=Severity.ERROR,
        message="dead rung",
        occurrence="rot180",
    )
    lsp_diag = to_lsp(diag, uri="file:///x.ladder")
    assert lsp_diag.severity == 1
    assert lsp_diag.code == "rung-referenced[rot180]"
    assert (lsp_diag.range.start.line, lsp_diag.range.start.character) == (4, 2)
    assert (lsp_diag.range.end.line, lsp_diag.range.end.character) == (4, 9)
    assert lsp_diag.source == "ladder"


def test_cheap_tier_stays_fast_on_largest_ladder() -> None:
    # The parse+resolve tier is what the server runs per keystroke; it must stay well under a frame.
    # (The full lint is seconds on al14 -- see the recorded baseline below -- which is exactly why the
    # server gates it behind open/save.)
    source = ladder_paths()[_LARGEST].read_text()
    lint_source(source, run_lint=False)  # warm
    start = time.perf_counter()
    lint_source(source, run_lint=False)
    elapsed = time.perf_counter() - start
    print(f"\n[latency] parse+resolve (cheap tier) of {_LARGEST}: {elapsed * 1000:.2f} ms")
    assert elapsed < 0.5


def test_full_lint_baseline_recorded() -> None:
    # Recorded, not gated: informs the debounce/tier policy. Generous backstop, not a target.
    source = ladder_paths()[_LARGEST].read_text()
    start = time.perf_counter()
    lint_source(source, run_lint=True)
    elapsed = time.perf_counter() - start
    print(f"\n[latency] full parse+resolve+lint of {_LARGEST}: {elapsed * 1000:.1f} ms")
    assert elapsed < 30.0


_TYPE_ERROR_LADDER = """ladder tmp-test
config {
    budget.depth_limit: 2
}
floor tmp-L0 {
    use flip_h: (Grid) -> Grid
}
rung {
    twice(g: Grid) -> Grid = flip_h(flip_h(g))
    task t1 {
        solution: twice(input)
        train [[1, 2], [3, 4]]
        test  [[5, 6], [7, 8]]
    }
}
top {
    task top1 {
        solution: flip_h(1)
        train [[1, 2], [3, 4]]
        test  [[5, 6], [7, 8]]
    }
}
"""


def test_type_error_in_a_solution_squiggles_the_expression_not_the_line() -> None:
    # `flip_h(1)` is a type error (int literal in a Grid slot). E1: it anchors to the solution
    # expression's exact span (mapped through solution_map), not the whole line and not line 0.
    diags = [d for d in lint_source(_TYPE_ERROR_LADDER) if d.severity is Severity.ERROR]
    assert len(diags) == 1
    diag = diags[0]
    assert diag.range.start.line == diag.range.end.line
    assert diag.range.start.character > 0  # precise: past the "solution: " prefix
    lines = _TYPE_ERROR_LADDER.splitlines()
    token = lines[diag.range.start.line][diag.range.start.character : diag.range.end.character]
    assert token == "flip_h(1)", token


def test_diagnostics_to_json_is_lsp_shaped() -> None:
    from arc_lab.program_search.ladders.pipeline import diagnostics_to_json

    diags = [
        LadderDiagnostic(
            code="rung-referenced",
            range=Range(Position(3, 4), Position(3, 10)),
            severity=Severity.ERROR,
            message="dead rung",
            occurrence="rot180",
        )
    ]
    payload = diagnostics_to_json(diags, path="al1.ladder")
    assert payload["path"] == "al1.ladder"
    assert payload["outcome"] == "failed"  # an error present
    entries = payload["diagnostics"]
    assert isinstance(entries, list)
    (entry,) = entries
    assert entry == {
        "code": "rung-referenced",
        "severity": "error",
        "message": "dead rung",
        "occurrence": "rot180",
        "range": {
            "start": {"line": 3, "character": 4},
            "end": {"line": 3, "character": 10},
        },
    }
    # No diagnostics -> clean.
    assert diagnostics_to_json([], path="x.ladder")["outcome"] == "clean"


def test_lsp_diagnostic_carries_both_the_slug_and_the_structured_pair() -> None:
    # The Problems panel prints `code`, so it gets the informative slug; the stable code and its
    # occurrence also travel structurally in `data`, so nothing has to parse the slug back apart.
    diag = LadderDiagnostic(
        code="jump-affordable",
        range=Range(Position(1, 0), Position(1, 4)),
        severity=Severity.ERROR,
        message="needs depth_limit 3, have 2",
        occurrence="rot180",
    )
    lsp_diag = to_lsp(diag, uri="file:///x.ladder")
    assert lsp_diag.code == "jump-affordable[rot180]"
    assert lsp_diag.data == {"code": "jump-affordable", "occurrence": "rot180"}
