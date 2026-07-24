"""``CHECK_PLAN``: the check registry's own invariants.

The lint is now data -- an ordered tuple of :class:`LadderCheck` instances -- so the properties
that used to be enforced by reading a 470-line method are assertions here instead: every check
declares its metadata, codes are unique, the skipped-checks list follows from the plan rather than
being maintained beside it, and no finding can carry a code no check owns.
"""

from __future__ import annotations

import pytest

from arc_lab.program_search.ladders.checks import CHECK_PLAN, CORPUS_CODES, LadderCheck
from arc_lab.program_search.ladders.checks.base import Category, CheckStage
from arc_lab.program_search.ladders.registry import make_ladder

#: The corpus-gated families, in the order the pre-registry ``lint()`` appended them by hand.
#: ``CORPUS_CODES`` is now derived from the plan; this pins it to the historical list.
_HISTORICAL_SKIPPED = (
    "tasks-exist",
    "min-2-train-examples",
    "rewrite-shallow",
    "distinct-train-inputs",
    "outputs-vary",
    "not-identity",
    "heldout-distinct",
    "constant-subterm",
    "if-condition-varies",
    "mdl-break-even",
)


def test_every_check_declares_its_metadata() -> None:
    for check in CHECK_PLAN:
        assert isinstance(check, LadderCheck)
        assert check.code and check.code == check.code.strip()
        assert isinstance(check.category, Category)
        assert isinstance(check.stage, CheckStage)
        assert check.default_severity in {"error", "warn"}
        assert check.summary.endswith("."), f"{check.code}: summary should be a sentence"


def test_codes_are_unique() -> None:
    codes = [check.code for check in CHECK_PLAN]
    assert len(codes) == len(set(codes)), f"duplicate check codes: {sorted(codes)}"


def test_skipped_checks_are_derived_from_the_plan_in_historical_order() -> None:
    # The structural tier names exactly the corpus-gated codes, in plan order -- a list that used
    # to be appended by hand next to each gated block and could drift from what was really skipped.
    assert CORPUS_CODES == _HISTORICAL_SKIPPED
    structural = make_ladder("al1-mirror").lint(corpus_backed=False)
    assert structural.skipped_checks == _HISTORICAL_SKIPPED


def test_the_plan_owns_every_code_a_lint_emits() -> None:
    # No finding may carry a code no check declares: `finding()` stamps the class body's `code`,
    # so this holds by construction -- and would break loudly if a check ever hand-built a slug.
    owned = {check.code for check in CHECK_PLAN}
    for name in ("al1-mirror", "al7-fast-tower"):
        emitted = {f.code for f in make_ladder(name).lint().findings}
        assert emitted <= owned, f"{name}: unowned codes {sorted(emitted - owned)}"


def test_a_check_cannot_omit_its_logic() -> None:
    # The ABC contract: `run` is abstract, so a check class that declares metadata but implements
    # nothing is a construction-time error, not a silently-passing check.
    class Incomplete(LadderCheck):
        code = "incomplete"
        category = Category.STRUCTURE
        stage = CheckStage.STRUCTURAL
        summary = "Never runs."

    with pytest.raises(TypeError, match="abstract"):
        Incomplete()  # type: ignore[abstract]


def test_severity_defaults_are_stamped_from_the_class_body() -> None:
    advisory = next(c for c in CHECK_PLAN if c.code == "floor-fully-exercised")
    assert advisory.finding(False, "x").severity == "warn"
    error = next(c for c in CHECK_PLAN if c.code == "rung-referenced")
    assert error.finding(False, "x", subject="r1").slug == "rung-referenced[r1]"
    assert error.finding(False, "x").severity == "error"
