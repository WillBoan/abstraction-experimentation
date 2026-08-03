"""``run_batch``: many Ladders as one coherent pass, and the checks that make it a batch of record.

The census's finding was not that any single ladder was wrong but that no two of them were run
together, so the pass itself -- and the single-generation check over it -- is the deliverable.
"""

from __future__ import annotations

import re
from pathlib import Path

from arc_lab.program_search.ladders.batch import (
    EXCLUDED,
    BatchMember,
    batch_members,
    render_manifest,
    run_batch_member,
)
from arc_lab.program_search.ladders.registry import ladder_paths


def test_membership_is_declared_and_every_exclusion_names_a_real_ladder() -> None:
    """Membership is a decision, so it is written down -- and an exclusion for a ladder that does
    not exist would silently shrink the batch."""
    registry = set(ladder_paths())
    assert set(EXCLUDED) <= registry
    members = set(batch_members())
    assert members == registry - set(EXCLUDED)
    assert members, "the batch cannot be empty"
    # Every exclusion states a reason; a bare name would be exactly the undocumented drift the
    # census found in the register.
    assert all(reason.strip() for reason in EXCLUDED.values())


def test_skip_and_only_narrow_the_pass() -> None:
    assert batch_members(only=["al21-dag-siblings"]) == ["al21-dag-siblings"]
    assert "al21-dag-siblings" not in batch_members(skip=["al21-dag-siblings"])


def test_a_member_that_raises_is_recorded_not_propagated(tmp_path: Path) -> None:
    """A 32-member pass that aborts on member 7 leaves a half-updated register."""
    member = run_batch_member("no-such-ladder", runs_root=tmp_path)

    assert member.error is not None and "no-such-ladder" in member.error
    assert member.admitted is None and member.rungs_total == 0


def test_an_arm_applies_its_override_to_the_member(tmp_path: Path) -> None:
    """The surface `run-ladder` had no way to express, and what a governance ablation needs."""
    baseline = run_batch_member("al21-dag-siblings", runs_root=tmp_path)
    arm = run_batch_member(
        "al21-dag-siblings",
        overrides={"learn.learn_engine.metric": "TwoPartMDL"},
        runs_root=tmp_path,
    )

    assert baseline.rungs_recovered == 2 and baseline.diagnoses == ()
    # Under a two-part code that charges definition size, nothing pays at this occurrence count --
    # so sleep correctly mints nothing, and the diagnosis says preference, not failure.
    assert arm.rungs_recovered == 0
    assert arm.diagnoses == ("proposed-not-selected",)
    # The override changed run identity, so the arm is a different generation from the baseline.
    assert baseline.generations != arm.generations


def test_artifacts_are_written_only_when_a_root_is_given(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    run_batch_member("al21-dag-siblings", runs_root=tmp_path, artifacts_root=root)

    written = root / "al21-dag-siblings"
    assert {p.name for p in written.iterdir()} == {"spec.md", "results.md", "report.json"}


def test_a_ladder_that_never_climbed_shows_no_climb_reading() -> None:
    """`n/a` (never ran, by design) must not read as `censored` (ran and was cut off)."""
    rejected = BatchMember(name="r", seconds=1.0, admitted=False, climbed=False, top_chain=True)
    climbed = BatchMember(
        name="c", seconds=1.0, admitted=True, climbed=True, top_chain=True, top_climb=None
    )
    text = re.sub(r" +", " ", render_manifest([rejected, climbed]))

    assert "| yes / n/a |" in text
    assert "| yes / censored |" in text


def test_manifest_reports_the_single_generation_check() -> None:
    """The check that separates a batch of record from a pile of runs."""
    members = [
        BatchMember(name="clean", seconds=1.0, admitted=True, generations=("aaa budget",)),
        BatchMember(
            name="mixed", seconds=2.0, admitted=True, generations=("aaa budget", "bbb budget")
        ),
        BatchMember(name="broke", seconds=0.5, error="Traceback ..."),
    ]
    text = render_manifest(members)

    assert "Members run: **3**" in text
    assert "Members that raised: **1**" in text and "`broke`" in text
    assert "span MORE THAN ONE config generation: **1**" in text and "`mixed`" in text
    assert "## Excluded from the batch, and why" in text


def test_an_arms_manifest_says_so_and_refuses_to_be_read_as_the_register() -> None:
    text = render_manifest(
        [BatchMember(name="x", seconds=1.0, admitted=True, generations=("a",))],
        arm="learn.learn_engine.metric=TwoPartMDL",
    )

    assert "ARM: learn.learn_engine.metric=TwoPartMDL" in text
    assert "**This is an ARM, not the batch of record.**" in text
    assert "never mixed into the register" in text
