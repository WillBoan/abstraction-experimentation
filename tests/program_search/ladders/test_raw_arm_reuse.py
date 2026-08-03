"""The raw arm's guard is a MEASURED quantity, so it lands in ``run_id`` and drifts.

``guard = ceil(k x laddered_marginal / |top tasks|)``: any change to the chain's cost mints a new
identity for the same enumeration. Measured 2026-08-03 -- ``94f9d214-nor-recolor`` and
``fafffa47-nor-recolor`` each bought their arm twice (1.2M then 5.2M considered), the smaller run
wholly contained in the larger. A recorded arm stopped no earlier than the one we need is a
strictly stronger substitute; these pin that it is found, and that only genuine dominators count.
"""

from __future__ import annotations

from pathlib import Path

from arc_lab.program_search.ladders.batch import RAW_ARM_MEMBERS, raw_arm_k_for
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.ladders.run import (
    RawArm,
    _laddered_marginal,
    dominating_raw_arm,
    run_ladder_chain,
    run_raw_arm,
)

#: Cheap, admitted, and its raw arm solves outright (13 considered) -- so a full purchase is fast.
LADDER = "al2-rot90-calibration"


def _arm(tmp_path: Path, k: int, *, reuse: bool = True) -> RawArm | None:
    spec = make_ladder(LADDER)
    chain = run_ladder_chain(spec, runs_root=tmp_path)
    marginal = _laddered_marginal(spec, chain.oracle_chain)
    return run_raw_arm(spec, marginal, k=k, runs_root=tmp_path, reuse=reuse)


def test_a_recorded_arm_with_a_bigger_guard_is_reused(tmp_path: Path) -> None:
    """The drift case: buy once at a high guard, then need a lower one."""
    big = _arm(tmp_path, k=10)
    assert big is not None and big.reused is False

    small = _arm(tmp_path, k=2)
    assert small is not None
    assert small.reused is True
    # Same recorded run, and the guard in force is the RECORDED one, not the one asked for.
    assert small.record.run_id == big.record.run_id
    assert small.guard_per_task == big.guard_per_task


def test_reuse_can_be_refused_for_an_exact_purchase(tmp_path: Path) -> None:
    _arm(tmp_path, k=10)
    exact = _arm(tmp_path, k=2, reuse=False)

    assert exact is not None and exact.reused is False


def test_a_smaller_recorded_guard_does_not_qualify(tmp_path: Path) -> None:
    """A run stopped EARLIER cannot stand in: censoring at a lower guard proves a weaker bound
    than the one being asked for, so the reuse must be refused and the search actually run."""
    small = _arm(tmp_path, k=2)
    assert small is not None and small.reused is False

    big = _arm(tmp_path, k=10)
    assert big is not None
    assert big.reused is False, "a lower-guarded run must not satisfy a higher guard"
    assert big.record.run_id != small.record.run_id


def test_an_empty_store_has_nothing_to_reuse(tmp_path: Path) -> None:
    assert dominating_raw_arm.__doc__  # the reasoning is load-bearing; keep it documented
    spec = make_ladder(LADDER)
    chain = run_ladder_chain(spec, runs_root=tmp_path)
    marginal = _laddered_marginal(spec, chain.oracle_chain)
    arm = run_raw_arm(spec, marginal, k=10, runs_root=tmp_path / "empty")

    assert arm is not None and arm.reused is False


def test_raw_arms_are_purchased_once_per_cohort_not_once_per_member() -> None:
    """The RQ1 protocol (`batch.py::RAW_ARM_MEMBERS`): purchased once per cohort, on the 4-rung
    member only; the
    2-rung members run ``--raw-arm-k 0``". Same task + floor + `d_raw` is the same search, so a
    per-member arm re-buys it AND manufactures ratios the cohort rule forbids comparing."""
    # The three real cohorts buy exactly one arm each.
    assert raw_arm_k_for("94f9d214-nor-recolor", default_k=10, no_raw_arms=False) == 10
    assert raw_arm_k_for("94f9d214-nor-halves", default_k=10, no_raw_arms=False) == 0
    assert raw_arm_k_for("94f9d214-nor-merged", default_k=10, no_raw_arms=False) == 0
    assert raw_arm_k_for("dae9d2b5-split-halves-lean", default_k=10, no_raw_arms=False) == 0
    # Synthetic ladders are single-member cohorts, so each carries its own.
    assert raw_arm_k_for("al17-shift-frame-tall", default_k=10, no_raw_arms=False) == 10
    # And the iteration-pass escape hatch turns them all off.
    assert all(
        raw_arm_k_for(name, default_k=10, no_raw_arms=True) == 0
        for name in [*RAW_ARM_MEMBERS, "al1-mirror", "94f9d214-nor-halves"]
    )
