"""Loading a `.ladder` file: parse -> resolve -> tasks + ``LadderSpec`` (LADDER-FORMAT.md).

The load-bearing test is :func:`test_every_ladder_regenerates_its_committed_testbed`: a `.ladder`
file is now the ONLY source of its ladder, so regenerating must reproduce the committed testbed
exactly -- the drift guard that replaced the per-ladder Python modules.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arc_lab.program_search.ladders.lang import LadderFormatError
from arc_lab.program_search.ladders.lang.load import ladder_tasks, resolve
from arc_lab.program_search.ladders.lang.parse import parse_document
from arc_lab.program_search.ladders.registry import ladder_paths, load_ladder, make_ladder
from arc_lab.program_search.ladders.shape import LintFinding
from arc_lab.program_search.ladders.spec import DemonstrationKind

REPO = Path(__file__).resolve().parents[4]

_LINT_CACHE: dict[str, tuple[LintFinding, ...]] = {}


def _lint_findings(name: str) -> tuple[LintFinding, ...]:
    """One batch-wide lint sweep shared by the lock tests (linting all 20 is seconds, and
    three sweeps would be three times that for identical answers)."""
    if name not in _LINT_CACHE:
        _LINT_CACHE[name] = make_ladder(name).lint().findings
    return _LINT_CACHE[name]

MINIMAL = """
ladder t1

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
    task c {
        solution: flip_h(rot180(input))
        train [[1, 2], [3, 4]]
        test  [[5, 6], [7, 8]]
    }
}
"""


def _load(text: str) -> object:
    return resolve(parse_document(text))


# -- the batch locks: every ladder loads, and regenerates its committed testbed -----


def _committed_testbed(name: str) -> tuple[list[dict[str, str]], dict[str, object]]:
    """The committed testbed's manifest task list and its task bodies, straight off disk."""
    root = REPO / "testbeds" / name
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    entries: list[dict[str, str]] = manifest["tasks"]
    tasks = {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in (root / "tasks").glob("*.json")
    }
    return entries, tasks


@pytest.mark.parametrize("name", sorted(ladder_paths()))
def test_every_ladder_regenerates_its_committed_testbed(name: str) -> None:
    """The drift guard: a `.ladder` file is the testbed's source, so regenerating must reproduce
    exactly what is committed -- task ids, order, labels, splits, and every grid."""
    generated = ladder_tasks(load_ladder(name))
    entries, committed = _committed_testbed(name)
    assert [task.task_id for task in generated] == [entry["task_id"] for entry in entries]
    assert [(task.label, task.split) for task in generated] == [
        (entry["label"], entry["split"]) for entry in entries
    ]
    for task in generated:
        assert task.spec == committed[task.task_id], f"{name}/{task.task_id} differs"


@pytest.mark.parametrize("name", sorted(ladder_paths()))
def test_every_ladder_builds_a_spec(name: str) -> None:
    spec = make_ladder(name)
    assert spec.rungs and spec.top.task_ids
    assert len(spec.top.task_ids) == len(spec.top.reference_solutions)


def test_static_lint_records_the_batch_s_known_defects() -> None:
    """Batch health, pinned. Two controls fail by design (al10's sandwich is deliberately
    unenforced; al12's rung has one demonstration so nothing can antiunify). The rest fail on
    real defects the demonstration-plan checks found: al4 ships a heldout task byte-identical to
    a train task; al13 shows both rung colour parameters only at 0 -- which is why it recovered
    zero rungs. The `constant-subterm` rows are the literal-collapse law caught statically: al14's
    index arithmetic is train-constant (the 2026-07-21 probe diagnosis, now static), and al4/al5/
    al6's perceiver calls are train-constant on the flagged tasks -- which is why the certificate
    recorded skip paths there and al5 recovered zero rungs (search substitutes the enumerated
    literal for the perceiver). The `rewrite-shallow` rows are the equational skip paths caught
    statically, each with a behaviorally-confirmed witness: the al3/al7 self-similar doubling
    (`tall4 == stack2(stack2 g)` and kin, inherited verbatim by the al9/al11 controls), al6's
    hidden flip_h.flip_h cancellation (r1 contributes nothing to r2), and al10's deliberately
    reachable raw top (the control working as designed, now with the witness printed). Fixing
    any of these is a deliberate act; update this set then."""
    failing = {
        name: sorted(
            f.check for f in _lint_findings(name) if not f.ok and f.severity == "error"
        )
        for name in ladder_paths()
    }
    failing = {name: checks for name, checks in failing.items() if checks}
    assert set(failing) == {
        "al3-quad-symmetrize",
        "al4-mask-crop",
        "al5-perceiver-chain",
        "al6-mirror-tall",
        "al7-fast-tower",
        "al9-decoy",
        "al10-skippable",
        "al11-greedy-trap",
        "al12-unlearnable",
        "al13-symmetry-repair",
        "al14-cell-row-grid",
    }
    assert failing["al3-quad-symmetrize"] == ["rewrite-shallow[band]"]
    doubling = ["rewrite-shallow[tall4]", "rewrite-shallow[wide4]", "rewrite-shallow[wide8]"]
    assert failing["al7-fast-tower"] == doubling
    assert failing["al9-decoy"] == doubling  # inherited spine, identical collapse
    assert failing["al11-greedy-trap"] == doubling
    assert failing["al10-skippable"] == [
        "raw-intractable",
        "rewrite-shallow[rot90]",
        "top-double-jump-intractable",
    ]
    assert failing["al4-mask-crop"] == [
        "constant-subterm[flatten_content-00]",
        "constant-subterm[flatten_content-01]",
        "constant-subterm[nonbg_mask-00]",
        "constant-subterm[nonbg_mask-01]",
        "constant-subterm[stamp-00]",
        "constant-subterm[stamp-01]",
        "constant-subterm[top-00]",
        "heldout-distinct[nonbg_mask-heldout-00]",
    ]
    assert failing["al5-perceiver-chain"] == [
        "constant-subterm[swap_extremes-00]",
        "constant-subterm[swap_mirror-00]",
        "constant-subterm[swap_stack-00]",
        "constant-subterm[top-00]",
    ]
    assert failing["al6-mirror-tall"] == [
        "constant-subterm[norm_mirror-00]",
        "constant-subterm[norm_quad-00]",
        "constant-subterm[norm_stack-00]",
        "constant-subterm[top-00]",
        "rewrite-shallow[rot180]",
    ]
    assert failing["al14-cell-row-grid"] == [
        "constant-subterm[move_cell_up-00]",
        "constant-subterm[move_cell_up-01]",
        "constant-subterm[move_grid_up-00]",
        "constant-subterm[move_grid_up-01]",
        "constant-subterm[move_row_up-00]",
        "constant-subterm[move_row_up-01]",
        "constant-subterm[top-00]",
    ]
    assert failing["al13-symmetry-repair"] == [
        "free-param-varies[sym_both#1]",
        "free-param-varies[sym_h#1]",
    ]
    assert "mdl-break-even[rot90]" in failing["al12-unlearnable"]


def test_the_evaluation_backed_checks_batch_posture() -> None:
    """Where the new evaluation-backed checks fire, pinned batch-wide. `if-condition-varies` is
    dormant (no ladder uses branching). `constant-subterm` ERRORS only where an enumerated
    literal beats the subterm; al8 carries the same perceiver constancy at WARN tier because its
    config mints no constants -- the severity split is the law's "does the beating literal exist
    in this ladder's own search?" clause, working."""
    by_ladder = {name: _lint_findings(name) for name in ladder_paths()}
    assert not any(
        f.check.startswith("if-condition-varies") for findings in by_ladder.values() for f in findings
    )
    constancy_errors = {
        name
        for name, findings in by_ladder.items()
        for f in findings
        if f.check.startswith("constant-subterm") and not f.ok and f.severity == "error"
    }
    assert constancy_errors == {
        "al4-mask-crop",
        "al5-perceiver-chain",
        "al6-mirror-tall",
        "al14-cell-row-grid",
    }
    rewrite_errors = {
        name
        for name, findings in by_ladder.items()
        for f in findings
        if f.check.startswith("rewrite-shallow") and not f.ok
    }
    assert rewrite_errors == {
        "al3-quad-symmetrize",
        "al6-mirror-tall",
        "al7-fast-tower",
        "al9-decoy",
        "al10-skippable",
        "al11-greedy-trap",
    }
    al8_warns = [
        f.check
        for f in by_ladder["al8-lean-perceiver"]
        if f.check.startswith("constant-subterm") and not f.ok and f.severity == "warn"
    ]
    assert al8_warns == [
        "constant-subterm[swap_ext-00]",
        "constant-subterm[swap_mir-00]",
        "constant-subterm[swap_stk-00]",
        "constant-subterm[top-00]",
    ]


def test_the_demonstration_plan_checks_hold_across_the_batch() -> None:
    """Within-task variation used to be guaranteed by `taskgen`'s seed generator, which the
    `.ladder` migration retired -- so it is now only true if the lint says so."""
    variation = {"distinct-train-inputs", "outputs-vary", "not-identity"}
    offenders = [
        (name, f.check)
        for name in ladder_paths()
        for f in _lint_findings(name)
        if not f.ok and f.check.split("[")[0] in variation
    ]
    assert offenders == []


def test_al1_reference_config_carries_the_frozen_guard() -> None:
    budget = make_ladder("al1-mirror").reference_config.budget
    assert budget.considered_limit == 50_000
    assert budget.considered_limit_mode == "immediate"
    assert budget.solution_limit is None
    assert (budget.depth_limit, budget.max_arity, budget.max_pool) == (2, 2, 300)


# -- structure ----------------------------------------------------------------------


def test_minimal_document_loads() -> None:
    document = parse_document(MINIMAL)
    assert document.name == "t1"
    assert document.floor_name == "t1-L0"
    assert [entry.name for entry in document.floor] == ["flip_h", "flip_v"]
    assert [rung.name for rung in document.rungs] == ["rot180"]
    assert [task.task_id for task in document.tasks()] == ["a", "b", "c"]
    loaded = resolve(document)
    assert [library.name for library in loaded.libraries] == ["t1-L0", "t1-L0+rot180"]


def test_comments_and_continued_grid_literals_are_ignored_and_joined() -> None:
    text = MINIMAL.replace(
        "        train [[1, 2], [3, 4]]\n",
        "        # a comment\n        train [\n            [1, 2],\n            [3, 4],\n        ]\n",
        1,
    )
    assert resolve(parse_document(text)).solutions.keys() == {"a", "b", "c"}


@pytest.mark.parametrize(
    ("mutation", "replacement", "fragment"),
    [
        ("ladder t1", "ladder T1", "kebab-case"),
        ("ladder t1", "ladder t1 extra", "exactly one name"),
        ("floor t1-L0 {", "floor {", "carries its library name"),
        ("config {", "conf {", "config"),
        ("top {", "bottom {", "top"),
        ("        test  [[5, 6], [7, 8]]\n    }\n    task b", "    }\n    task b", "at least one"),
        ("    task a {\n        solution: rot180(input)", "    task a {\n", "comes first"),
        ("use flip_h: (Grid) -> Grid", "use flip_h: (Grid, Color) -> Grid", "the registry says"),
        ("use flip_h: (Grid) -> Grid", "use nope_h: (Grid) -> Grid", "unknown primitive"),
        ("task b {", "task a {", "duplicate task id"),
        ("budget.depth_limit: 2", "budget.depth_limit: 2\n    budget.depth_limit: 3", "duplicate"),
        ("budget.depth_limit: 2", "library: 'd4'", "not settable"),
        ("budget.depth_limit: 2", "budget.nope: 2", "unknown field"),
        ("budget.depth_limit: 2", "budget.depth_limit: two", "must be a literal"),
        ("rot180(g: Grid) -> Grid", "flip_h(g: Grid) -> Grid", "shadows the floor"),
        ("rot180(g: Grid) -> Grid = ", "rot180(g: Grid, x: Color) -> Grid = ", "never used"),
        ("rot180(g: Grid) -> Grid = ", "rot180(g: Grid) -> Color = ", "declared to return"),
    ],
)
def test_malformed_documents_are_rejected(mutation: str, replacement: str, fragment: str) -> None:
    with pytest.raises(LadderFormatError, match=fragment):
        _load(MINIMAL.replace(mutation, replacement, 1))


def test_a_demonstrating_task_must_call_its_rung() -> None:
    """The kind is derived from the call, so a solution that merely *inlines* the rung is a load
    error rather than a silently mis-typed demonstration (spec DRV-2)."""
    text = MINIMAL.replace(
        "        solution: rot180(input)\n        train [[1, 2]",
        "        solution: flip_h(flip_v(input))\n        train [[1, 2]",
        1,
    )
    with pytest.raises(LadderFormatError, match="never calls it"):
        _load(text)


def test_blocks_must_close_on_their_own_line() -> None:
    with pytest.raises(LadderFormatError, match="own line"):
        parse_document(
            MINIMAL.replace(
                "        test  [[5, 6], [7, 8]]\n    }", "        test  [[5, 6], [7, 8]] }", 1
            )
        )
    with pytest.raises(LadderFormatError, match="unclosed block"):
        parse_document(MINIMAL.rstrip()[:-1])


def test_errors_carry_their_line_number() -> None:
    text = MINIMAL.replace("use flip_v: (Grid) -> Grid", "use flip_v: (Grid, Color) -> Grid", 1)
    with pytest.raises(LadderFormatError) as excinfo:
        _load(text)
    assert excinfo.value.line == 10  # the `use flip_v` line
    assert "line 10" in str(excinfo.value)


# -- derived demonstration kinds (spec DRV-2) ---------------------------------------

_FRAGMENT = """
ladder t2

config {
    budget.depth_limit: 2
}

floor t2-L0 {
    use flip_h: (Grid) -> Grid
    use flip_v: (Grid) -> Grid
    use map_color: (Grid, Color, Color) -> Grid
}

rung {
    recol(g: Grid, c: Color) -> Grid = map_color(flip_h(g), c, 9)

    task a {
        solution: flip_v(recol(input, %s))
        train [[1, 2], [3, 4]]
        test  [[5, 6], [7, 8]]
    }
    task b {
        solution: flip_v(recol(input, %s))
        train [[2, 3], [4, 5]]
        test  [[6, 7], [8, 9]]
    }
    heldout task h {
        solution: flip_v(recol(input, 7))
        train [[3, 4], [5, 6]]
        test  [[7, 8], [9, 1]]
    }
}

top {
    task c {
        solution: flip_h(recol(input, 1))
        train [[1, 2], [3, 4]]
        test  [[5, 6], [7, 8]]
    }
}
"""


def test_a_rung_used_as_a_fragment_with_identical_arguments() -> None:
    demos = resolve(parse_document(_FRAGMENT % ("1", "1"))).demonstrations[0]
    assert [demo.task_id for demo in demos] == ["a", "b"]  # heldout is not a demonstration
    assert {demo.kind for demo in demos} == {DemonstrationKind.FRAGMENT_IDENTICAL}


def test_a_rung_used_as_a_fragment_with_varying_arguments() -> None:
    demos = resolve(parse_document(_FRAGMENT % ("1", "2"))).demonstrations[0]
    assert {demo.kind for demo in demos} == {DemonstrationKind.FRAGMENT_VARYING}


def test_heldout_tasks_do_not_vote_on_the_kind() -> None:
    """The heldout task passes 7 while both train tasks pass 1 -- the rung is still IDENTICAL,
    because a kind describes what sleep learns from (spec DRV-2)."""
    demos = resolve(parse_document(_FRAGMENT % ("1", "1"))).demonstrations[0]
    assert {demo.kind for demo in demos} == {DemonstrationKind.FRAGMENT_IDENTICAL}


def test_draft_spec_matches_the_committed_testbed_spec() -> None:
    """`lint-ladder` builds its corpus in memory so a DRAFT ladder can be checked before its
    testbed exists. That is only safe if the two agree -- pinned here for every ladder."""
    from arc_lab.program_search.ladders.lang.load import draft_spec, ladder_spec

    for name in sorted(ladder_paths()):
        loaded = load_ladder(name)
        draft, committed = draft_spec(loaded), ladder_spec(loaded)
        assert draft.train_corpus.content_hash() == committed.train_corpus.content_hash(), name
        assert draft.heldout_corpus.content_hash() == committed.heldout_corpus.content_hash(), name
        assert [(f.check, f.ok) for f in draft.lint().findings] == [
            (f.check, f.ok) for f in committed.lint().findings
        ], name
