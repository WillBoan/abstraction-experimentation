"""End-to-end lock for ladder #1 (``al1-mirror``): the climb + oracle chain + certificate + report.

Heavy (a full LEARN run + oracle chain), so ``slow`` -- runs in ``make check``, not ``make test``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.report import create_ladder_report
from arc_lab.program_search.ladders.run import run_ladder


@pytest.mark.slow
def test_ladder1_climbs_recovers_both_rungs_and_is_admitted(tmp_path: Path) -> None:
    result = run_ladder(make_ladder("al1-mirror"), runs_root=tmp_path)

    cert = result.certificate
    assert cert.admitted
    assert result.climbed  # admitted -> the climb stage ran
    assert cert.tractable_jumps == {1: True, 2: True}  # L0 solves rot180; L1 solves mirror_recolor
    assert cert.no_skip_paths == {1: True, 2: True}  # no rung is skippable; the top needs the chain
    assert cert.demonstration_health == {1: 1.0, 2: 1.0}

    report = create_ladder_report(result)
    climb = report["climb_trace"]
    assert isinstance(climb, list)
    # The wake-sleep loop mints exactly the two bridging rungs, one per iteration.
    minted = [
        name for entry in climb if isinstance(entry, dict) for name in entry.get("minted", [])
    ]
    assert minted == ["abs0", "abs1"]
    # Both are behavioral matches for the intended rungs.
    recovery = report["rung_recovery"]
    assert isinstance(recovery, list)
    assert all(isinstance(row, dict) and row["recovered"] for row in recovery)
    # The top is genuinely intractable raw at the reference budget -- the amortization is real.
    cost = report["cost"]
    shape = report["shape"]
    assert isinstance(cost, dict) and cost["raw_solved"] is False
    assert isinstance(shape, dict) and shape["lint_ok"] is True


def test_a_rejected_ladder_never_pays_for_the_climb(tmp_path: Path) -> None:
    # al10 is the control whose top is deliberately reachable without the rung (al2's floor at
    # depth_limit 4), so its certificate rejects on a skip path. Staged run_ladder must stop
    # there: no LEARN run, no off-chain run -- a rejected ladder costs exactly its oracle chain.
    # Fast: the floor generates the 8-element D4 group, so every chain search is tiny.
    result = run_ladder(make_ladder("al10-skippable"), runs_root=tmp_path)

    assert not result.certificate.admitted
    assert not result.climbed
    assert result.learn is None and result.off_chain is None

    # The chain-only report still carries everything stage 1 measures, and says plainly that the
    # climb-derived sections are absent rather than zero.
    report = create_ladder_report(result)
    assert report["climb_executed"] is False
    assert report["climb_trace"] == [] and report["rung_recovery"] == []
    cost = report["cost"]
    assert isinstance(cost, dict)
    assert cost["laddered_end_to_end_considered"] is None
    assert cost["off_chain_top_solved"] is None
    assert cost["jump_costs"]  # the chain's measurements are all present
    comparisons = report["comparisons"]
    assert isinstance(comparisons, dict) and comparisons["loop_overhead_factor"] is None


def test_climb_rejected_forces_the_climb_stage(tmp_path: Path) -> None:
    # The control-arm escape hatch (al8's head-to-head cost read is the intended user): the same
    # rejected ladder, forced -- the climb and off-chain runs happen despite the verdict.
    result = run_ladder(make_ladder("al10-skippable"), runs_root=tmp_path, climb_rejected=True)

    assert not result.certificate.admitted
    assert result.climbed
    assert result.learn is not None and result.off_chain is not None
    report = create_ladder_report(result)
    assert report["climb_executed"] is True
