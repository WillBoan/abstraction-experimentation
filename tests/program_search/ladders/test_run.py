"""End-to-end lock for ladder #1 (``al1-mirror``): the climb + oracle chain + certificate + report.

Heavy (a full LEARN run + oracle chain), so ``slow`` -- runs in ``make check``, not ``make test``.
"""

from __future__ import annotations

import dataclasses
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
    # Goal-reachability, surfaced beside the certificate because admission never asserts it: this
    # ladder reaches its top in BOTH stages -- the oracle chain's L_k search and the learned climb.
    reach = report["top_reachable"]
    assert reach == {"chain": True, "climb": True}
    # Uncompromised run -> the loop-overhead factor is present, not forfeited.
    comparisons = report["comparisons"]
    assert isinstance(comparisons, dict)
    assert isinstance(comparisons["loop_overhead_factor"], float)
    assert comparisons["loop_overhead_forfeited_by"] is None


def test_a_dag_is_certified_against_its_consumers_not_its_levels(tmp_path: Path) -> None:
    """The DAG end-to-end lock (``al21-dag-siblings``: two independent branches under one top).

    Both readings of "the layer above rung i" agree on a chain, so the whole al1-al20 batch could
    not tell them apart. Here they disagree, and the level reading fails in BOTH directions at once:

    - ``no_skip_paths[1]`` would probe rung 2's tasks under ``L_0`` -- and rung 2 composes over the
      bare floor, so ``L_0`` solves them trivially and the ladder is REJECTED for a "skip path"
      that is really just a sibling being independently reachable;
    - ``demonstration_health[2]`` would demand rung 2's retained solution call rung 1, which it has
      no reason to do, scoring a correct ladder 0.0.

    Cheap by construction (a 4-primitive floor at ``depth_limit`` 2), because the real-task DAG
    that exposed this (``dae9d2b5-halves-union``) is a multi-hour chain and can guard nothing here.
    """
    result = run_ladder(make_ladder("al21-dag-siblings"), runs_root=tmp_path)

    shape = result.shape
    assert shape.is_chain is False
    assert shape.depth_schedule == (2, 2, 2)

    cert = result.certificate
    assert cert.no_skip_paths == {1: True, 2: True}  # both probe the TOP, their actual consumer
    assert cert.demonstration_health == {1: 1.0, 2: 1.0}  # neither branch depends on the other
    assert cert.tractable_jumps == {1: True, 2: True}
    assert cert.admitted and result.climbed

    report = create_ladder_report(result)
    recovery = report["rung_recovery"]
    assert isinstance(recovery, list)
    assert all(isinstance(row, dict) and row["recovered"] for row in recovery)
    # The report's marginal-value view names the consumer too, not `rungs[i]`: on this shape both
    # rungs' layer above is the top, and rung 1's is NOT "mirror_flip".
    comparisons = report["comparisons"]
    assert isinstance(comparisons, dict)
    rung_value = comparisons["marginal_rung_value"]
    assert isinstance(rung_value, list)
    assert [row["layer_above"] for row in rung_value] == ["top", "top"]


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


@pytest.mark.slow
def test_solution_limit_forfeits_the_loop_overhead_factor(tmp_path: Path) -> None:
    """The solution-limit Compromise Option's registry entry names the loop-overhead factor
    forfeited (found by measurement 2026-07-27: the chain and the climb truncate at different
    points under an early stop, and a member reported end-to-end BELOW marginal, 0.30x). The
    report enforces the registry instead of leaving the invalid ratio for a reader to quote."""
    spec = make_ladder("al1-mirror")
    budget = dataclasses.replace(
        spec.reference_config.budget, solution_limit=1, solution_limit_mode="immediate"
    )
    early = dataclasses.replace(spec, reference_config=spec.reference_config.with_(budget=budget))
    report = create_ladder_report(run_ladder(early, runs_root=tmp_path))
    compromises = report["compromises"]
    assert isinstance(compromises, list)
    assert "solution-limit" in [c["code"] for c in compromises if isinstance(c, dict)]
    comparisons = report["comparisons"]
    assert isinstance(comparisons, dict)
    assert comparisons["loop_overhead_factor"] is None
    assert comparisons["loop_overhead_forfeited_by"] == ["solution-limit"]


def test_climb_rejected_forces_the_climb_stage(tmp_path: Path) -> None:
    # The control-arm escape hatch (al8's head-to-head cost read is the intended user): the same
    # rejected ladder, forced -- the climb and off-chain runs happen despite the verdict.
    result = run_ladder(make_ladder("al10-skippable"), runs_root=tmp_path, climb_rejected=True)

    assert not result.certificate.admitted
    assert result.climbed
    assert result.learn is not None and result.off_chain is not None
    report = create_ladder_report(result)
    assert report["climb_executed"] is True


def test_the_raw_arm_measures_al2s_ratio_and_it_is_honest(tmp_path: Path) -> None:
    # al2 is the trivial-regime instrument: its D4 floor makes raw genuinely cheap, so the arm
    # SOLVES and RQ1 is a measured ratio -- and it is BELOW 1 (raw-to-first 13 vs laddered 27):
    # al2's ladder does not pay for itself, which is the honest reading the retired estimator
    # (raw "estimated" at 31) could never establish. Decision 1's solve branch, end to end.
    result = run_ladder(make_ladder("al2-rot90-calibration"), runs_root=tmp_path)

    arm = result.raw_arm
    assert arm is not None
    assert arm.laddered_marginal > 0
    assert arm.guard_per_task == 10 * arm.laddered_marginal  # one top task: guard = k x M
    report = create_ladder_report(result)
    cost = report["cost"]
    assert isinstance(cost, dict)
    view = cost["raw_arm"]
    assert isinstance(view, dict)
    assert view["solved"] is True and view["sound"] is True
    assert view["amortization_ratio_kind"] == "measured"
    ratio = view["amortization_ratio"]
    assert isinstance(ratio, float) and ratio < 1.0


def test_a_censoring_raw_arm_is_a_lower_bound_not_a_measurement(tmp_path: Path) -> None:
    # Force the censor branch by sizing the guard below raw's cost-to-first (a doctored marginal
    # of 1 at k=1): the arm spends its guard without solving, and the report labels the ratio a
    # LOWER BOUND -- never "measured".
    import dataclasses

    from arc_lab.program_search.ladders.run import run_raw_arm

    spec = make_ladder("al2-rot90-calibration")
    result = run_ladder(spec, runs_root=tmp_path)
    # `reuse=False` is required to CONSTRUCT this scenario: `run_ladder` above already recorded a
    # properly-guarded arm that solved, and reuse would (correctly) serve that stronger result
    # instead of a deliberately under-guarded one. Fabricating a weaker arm is a test affordance,
    # never something a real run wants.
    tiny = run_raw_arm(spec, 1, k=1, runs_root=tmp_path, reuse=False)
    assert tiny is not None and tiny.guard_per_task == 1

    report = create_ladder_report(dataclasses.replace(result, raw_arm=tiny))
    cost = report["cost"]
    assert isinstance(cost, dict)
    view = cost["raw_arm"]
    assert isinstance(view, dict)
    assert view["solved"] is False
    assert view["amortization_ratio_kind"] == "lower-bound"
    assert view["spend_considered"] == 1  # exactly the guard: `immediate` censoring is exact


def test_the_raw_arm_refuses_to_run_unguarded() -> None:
    # No measured laddered cost (or k < 1) -> nothing to size the spend against -> no arm.
    # An unguarded raw run is exactly what decision 1 forbids.
    from arc_lab.program_search.ladders.run import run_raw_arm

    spec = make_ladder("al2-rot90-calibration")
    assert run_raw_arm(spec, 0, k=10) is None
    assert run_raw_arm(spec, 100, k=0) is None
