"""End-to-end lock for ladder #1 (``al1-mirror``): the climb + oracle chain + certificate + report.

Heavy (a full LEARN run + oracle chain), so ``slow`` -- runs in ``make check``, not ``make test``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arc_lab.program_search.ladders.certificate import certify
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.report import create_ladder_report
from arc_lab.program_search.ladders.run import run_ladder


@pytest.mark.slow
def test_ladder1_climbs_recovers_both_rungs_and_is_admitted(tmp_path: Path) -> None:
    result = run_ladder(make_ladder("al1-mirror"), runs_root=tmp_path)

    cert = certify(result)
    assert cert.admitted
    assert cert.tractable_jumps == {1: True, 2: True}  # L0 solves rot180; L1 solves mirror_recolor
    assert cert.no_skip_paths == {1: True, 2: True}  # no rung is skippable; the top needs the chain
    assert cert.demonstration_health == {1: 1.0, 2: 1.0}

    report = create_ladder_report(result)
    climb = report["climb_trace"]
    assert isinstance(climb, list)
    # The wake-sleep loop mints exactly the two bridging rungs, one per iteration.
    minted = [name for entry in climb if isinstance(entry, dict) for name in entry.get("minted", [])]
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
