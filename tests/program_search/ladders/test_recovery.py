"""Rung recovery's diagnosis: WHERE the pipeline broke when a rung was not recovered.

The three mechanisms rendered identically before 2026-08-03 -- proposer reach, governance
preference, and no material -- are entirely different defects, and one of them is not a defect at
all. Every case below is driven through the real engine on ``al21-dag-siblings`` (the batch's cheap
admitted DAG, ~0.2s) or a control, never a hand-built fixture: the point is that the diagnosis
matches what the machinery actually does.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from arc_lab.program_search.execution.overrides import apply_overrides
from arc_lab.program_search.ladders.recovery import (
    NOT_PROPOSED,
    PROPOSED_NOT_SELECTED,
    rung_recovery_rows,
)
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.run import LadderResult, run_ladder
from arc_lab.program_search.ladders.spec import LadderSpec


def _with(name: str, **overrides: str) -> LadderSpec:
    spec = make_ladder(name)
    return dataclasses.replace(
        spec, reference_config=apply_overrides(spec.reference_config, dict(overrides))
    )


def _rows(spec: LadderSpec, tmp_path: Path, **kwargs: bool) -> list[dict[str, object]]:
    result: LadderResult = run_ladder(spec, runs_root=tmp_path, **kwargs)
    return rung_recovery_rows(result)


def test_a_recovered_rung_carries_no_diagnosis(tmp_path: Path) -> None:
    rows = _rows(make_ladder("al21-dag-siblings"), tmp_path)

    assert [row["rung"] for row in rows] == ["mirror_h", "mirror_flip"]
    assert all(row["recovered"] for row in rows)
    assert all(row["not_recovered_because"] is None for row in rows)
    assert all(row["matched_by"] for row in rows)


def test_proposer_reach_failure_reads_as_not_proposed(tmp_path: Path) -> None:
    """`FrequentSubtree` mines ``walk()[1:]`` -- each program's own ROOT excluded -- so a rung
    demoed as a full solution is the one template it can never offer. Measured 2026-07-27 as 0/4,
    0/5, 0/2; here the report names the mechanism instead of just the zero."""
    rows = _rows(
        _with("al21-dag-siblings", **{"learn.learn_engine.proposer": "FrequentSubtree"}), tmp_path
    )

    assert not any(row["recovered"] for row in rows)
    assert all(row["not_recovered_because"] == NOT_PROPOSED for row in rows)
    assert all(row["proposed_at_iteration"] is None for row in rows)


def test_al12s_designed_failure_is_named_as_proposer_reach(tmp_path: Path) -> None:
    """The control's own design note is "rot90 has ONE demo, so ``AntiunifyPairs`` has nothing to
    pair" -- an independent check that the diagnosis names the real mechanism."""
    rows = _rows(make_ladder("al12-unlearnable"), tmp_path, climb_rejected=True)

    assert [row["recovered"] for row in rows] == [False]
    assert rows[0]["not_recovered_because"] == NOT_PROPOSED


def test_governance_preference_reads_as_proposed_not_selected(tmp_path: Path) -> None:
    """The verdict a governance-objective arm exists to produce, and the reason this distinction
    blocks such an arm: under a two-part code that charges definition size, few occurrences cannot
    pay for any abstraction, so sleep correctly mints NOTHING. The proposer still offered the
    rungs -- so this is preference, not reach, and 'the learner failed' would be the wrong reading
    (`experiments/2026-07-27-half-param-governance/`)."""
    rows = _rows(
        _with("al21-dag-siblings", **{"learn.learn_engine.metric": "TwoPartMDL"}), tmp_path
    )

    assert not any(row["recovered"] for row in rows)
    assert all(row["not_recovered_because"] == PROPOSED_NOT_SELECTED for row in rows)
    # Offered at iteration 0 and discarded -- the material was there and reachable.
    assert all(row["proposed_at_iteration"] == 0 for row in rows)


def test_recovery_is_absent_not_zero_when_the_climb_never_ran(tmp_path: Path) -> None:
    """A rejected ladder's rungs were never offered to a learner, so "not recovered" would be a
    claim about nothing."""
    result = run_ladder(make_ladder("al10-skippable"), runs_root=tmp_path)

    assert not result.climbed
    assert rung_recovery_rows(result) == []
