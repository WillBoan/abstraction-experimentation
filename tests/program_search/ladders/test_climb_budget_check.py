"""``climb-budget-covers-top``: the pinned ``depth_limit`` is the CLIMB's search budget, and a
pinned value below the derived schedule's maximum leaves the goal structurally inexpressible to
the learner -- the defect class found three times on 2026-07-27 (``dae9d2b5-split-asym-lean``,
both NOR ``-halves`` members)."""

from __future__ import annotations

from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.shape import LintFinding


def _verdicts(name: str) -> list[LintFinding]:
    shape = make_ladder(name).lint(corpus_backed=False)
    return [f for f in shape.findings if f.code == "climb-budget-covers-top"]


def test_flags_a_pinned_limit_below_the_derived_schedule() -> None:
    # `94f9d214-nor-halves` pins depth_limit 3 against a depth-4 top (schedule [2,2,4]), so its
    # climb can never express the goal. Warn severity: whether goal-reachability should GATE
    # admission is an open design decision; the misconfiguration is named the moment it exists.
    findings = _verdicts("94f9d214-nor-halves")
    assert [f.ok for f in findings] == [False]
    assert findings[0].severity == "warn"


def test_passes_when_the_pinned_limit_covers_the_schedule() -> None:
    # All-depth-2 member pinning 2: the climb's budget covers every level.
    assert [f.ok for f in _verdicts("dae9d2b5-split-recolor-lean")] == [True]


def test_a_pinned_schedule_passes_trivially() -> None:
    # Under PINNED mode the schedule IS the pinned value everywhere (al10's uniform budget is its
    # content), so the check cannot fire.
    assert [f.ok for f in _verdicts("al10-skippable")] == [True]
