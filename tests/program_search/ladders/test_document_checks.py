"""The ``stage=SYNTAX`` checks: pure predicates over the parsed document.

Two consumers, one definition -- so both are pinned here. The strict loader must raise exactly the
message and line it always did (these rules used to be inline `raise`s in ``load.py``), and the
editor must report ALL of them at once, each on its own exact span.
"""

from __future__ import annotations

import pytest

from arc_lab.program_search.ladders.checks.plan import DOCUMENT_PLAN
from arc_lab.program_search.ladders.checks.run import check_document
from arc_lab.program_search.ladders.lang.errors import LadderFormatError
from arc_lab.program_search.ladders.lang.load import resolve
from arc_lab.program_search.ladders.lang.parse import parse_document
from arc_lab.program_search.ladders.pipeline import lint_source
from arc_lab.program_search.ladders.registry import ladder_paths

_CLEAN = """ladder t1

config {
    budget.depth_limit: 2
}

floor t1-L0 {
    use flip_h: (Grid) -> Grid
    use flip_v: (Grid) -> Grid
}

rung {
    rot180(g: Grid) -> Grid = flip_h(flip_v(g))

    task a {
        solution: rot180(input)
        train [[1, 2], [3, 4]]
        test  [[5, 6], [7, 8]]
    }
    task b {
        solution: rot180(input)
        train [[2, 3], [4, 5]]
        test  [[6, 7], [8, 9]]
    }
}

top {
    task top-00 {
        solution: flip_h(rot180(input))
        train [[1, 2], [3, 4]]
        test  [[5, 6], [7, 8]]
    }
}
"""


def _text_at(source: str, finding_anchor: object) -> str:
    from arc_lab.program_search.ladders.diagnostics import Range

    assert isinstance(finding_anchor, Range)
    line = source.splitlines()[finding_anchor.start.line]
    return line[finding_anchor.start.character : finding_anchor.end.character]


def test_every_registry_ladder_passes_the_syntax_checks() -> None:
    # These are findings-only checks: a well-formed file produces nothing at all.
    for name, path in ladder_paths().items():
        document = parse_document(path.read_text())
        assert check_document(document) == [], name


@pytest.mark.parametrize(
    ("mutation", "replacement", "detail", "anchored_on"),
    [
        (
            "    use flip_v: (Grid) -> Grid\n",
            "    use flip_h: (Grid) -> Grid\n",
            "duplicate floor primitive 'flip_h'",
            "flip_h",
        ),
        (
            "    budget.depth_limit: 2\n",
            "    budget.depth_limit: 2\n    budget.depth_limit: 3\n",
            "duplicate config path 'budget.depth_limit'",
            "budget.depth_limit",
        ),
        ("    task b {", "    task a {", "duplicate task id 'a'", "a"),
    ],
)
def test_a_repeat_is_reported_on_its_own_token(
    mutation: str, replacement: str, detail: str, anchored_on: str
) -> None:
    source = _CLEAN.replace(mutation, replacement)
    (finding,) = check_document(parse_document(source))
    assert finding.detail == detail
    assert finding.anchor is not None
    assert _text_at(source, finding.anchor) == anchored_on


def test_the_loader_still_raises_the_first_failure_with_its_historical_line() -> None:
    # The rules moved out of `load.py`, but `resolve()` must be indistinguishable from before: the
    # same message, and the same 1-based line -- now derived from the check's own span.
    source = _CLEAN.replace("    task b {", "    task a {")
    with pytest.raises(LadderFormatError) as caught:
        resolve(parse_document(source))
    assert caught.value.detail == "duplicate task id 'a'"
    # The line is the REPEAT's, not the first declaration's -- which is what `load.py` reported
    # when it raised on `block.task_id in solutions`, i.e. on reaching the second block.
    repeats = [i for i, line in enumerate(source.splitlines(), start=1) if "task a {" in line]
    assert caught.value.line == repeats[-1]
    assert len(repeats) == 2  # the fixture really does declare it twice


def test_an_empty_floor_is_rejected_without_a_line() -> None:
    source = _CLEAN.replace("    use flip_h: (Grid) -> Grid\n", "").replace(
        "    use flip_v: (Grid) -> Grid\n", ""
    )
    with pytest.raises(LadderFormatError) as caught:
        resolve(parse_document(source))
    assert caught.value.detail == "the floor needs at least one primitive (spec FLR-3)"
    assert caught.value.line is None  # a whole-file defect names no line, exactly as before


def test_the_editor_reports_every_repeat_at_once() -> None:
    # The payoff of separating these: `resolve()` can only raise the first, but the editor shows
    # all three, each squiggling its own token instead of a whole line.
    source = (
        _CLEAN.replace("    use flip_v: (Grid) -> Grid\n", "    use flip_h: (Grid) -> Grid\n")
        .replace(
            "    budget.depth_limit: 2\n", "    budget.depth_limit: 2\n    budget.depth_limit: 3\n"
        )
        .replace("    task b {", "    task a {")
    )
    diagnostics = lint_source(source)
    assert [d.code for d in diagnostics] == [
        "floor-names-unique",
        "config-paths-unique",
        "task-ids-unique",
    ]
    assert all(d.range.start.character > 0 for d in diagnostics)  # precise, never a whole line


def test_the_document_plan_is_syntax_stage_throughout() -> None:
    from arc_lab.program_search.ladders.checks.base import CheckStage, DocumentCheck

    for check in DOCUMENT_PLAN:
        assert isinstance(check, DocumentCheck)
        assert check.stage is CheckStage.SYNTAX
        assert check.default_severity == "error"
