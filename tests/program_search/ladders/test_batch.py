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
from arc_lab.program_search.ladders.registry import ladder_paths, make_ladder


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


def test_cohorts_are_derived_so_a_shared_task_with_a_different_floor_splits() -> None:
    """A cohort is task AND Floor. `LADDER-RELATIONSHIPS-2026-07-23.md` rejected a *declared*
    cohort field precisely because it "would drift the moment a floor is edited" -- so the pair
    that must not silently merge is the real one: `dae9d2b5-halves-union` names a half through the
    region tier, its siblings through `split_h`. Subtracting across them would price a
    decomposition difference that is really a Floor difference."""
    union = make_ladder("dae9d2b5-halves-union")
    sibling = make_ladder("dae9d2b5-split-recolor")

    assert union.task == sibling.task == "dae9d2b5"
    assert union.cohort() and sibling.cohort()
    assert union.cohort() != sibling.cohort(), "different Floors must not share a cohort"
    # ...while the cohort template's two tasks, same Floor, land on the same Floor half.
    left, right = make_ladder("94f9d214-nor-merged"), make_ladder("fafffa47-nor-merged")
    assert left.cohort() != right.cohort()
    assert left.cohort().split("/")[1] == right.cohort().split("/")[1]


def test_a_synthetic_ladder_declares_no_task_and_stands_alone() -> None:
    """No external target means nothing to be comparable *to*: a cohort of one, so the RQ1 arm is
    bought per ladder rather than shared."""
    spec = make_ladder("al17-shift-frame-tall")
    assert spec.task == "" and spec.cohort() == ""


def test_manifest_rolls_up_what_the_batch_samples_not_just_per_member_rows() -> None:
    """The defect this fixes: every fact below was already in the per-member rows, machine-readably
    and repeated N times, and no artifact ever COUNTED them -- so "the whole set runs one learner"
    was invisible to a reader and had to be rediscovered by hand."""
    members = [
        BatchMember(
            name="climber",
            seconds=1.0,
            admitted=True,
            climbed=True,
            generations=("a",),
            report={
                "provenance": [
                    {
                        "cell": "chain/L0",
                        "budget": {"considered_limit": 50_000, "solution_limit": None},
                        "learn": None,
                    },
                    {
                        "cell": "climb/learn",
                        "budget": {"considered_limit": 50_000, "solution_limit": None},
                        "learn": {"metric": "CompressionMetric", "proposer": "AntiunifyPairs"},
                    },
                    # The raw arm carries its own measured guard, so counting it would report a
                    # `considered_limit` the ladder never ran its chain at.
                    {
                        "cell": "raw-arm",
                        "budget": {"considered_limit": 187_070, "solution_limit": 1},
                        "learn": None,
                    },
                ]
            },
        ),
        BatchMember(name="rejected", seconds=1.0, admitted=False, climbed=False, generations=("a",)),
    ]
    text = render_manifest(members)

    assert "**2 members: 1 climbed**" in text and "1 chain-only" in text
    assert "`CompressionMetric` (1)" in text and "`AntiunifyPairs` (1)" in text
    assert "`50000` (1)" in text and "187070" not in text, "the raw arm is generation-exempt"
    assert "`exhaustive` (1)" in text
    assert "An axis with one value is an assumption, not a result" in text


def test_manifest_states_the_generation_check_is_per_member_not_a_comparison_license() -> None:
    """The claim this replaces said the check is "what makes its cost columns comparable", which
    read as a cross-member license it never was -- the batch spans a 50k and a 2M guard."""
    text = render_manifest([BatchMember(name="x", seconds=1.0, admitted=True, generations=("a",))])

    assert "check on each member SEPARATELY" in text
    assert "not** what licenses comparing two members" in text
    assert "additionally needs a shared cohort" in text
