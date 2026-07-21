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
from arc_lab.program_search.ladders.spec import DemonstrationKind

REPO = Path(__file__).resolve().parents[4]

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


def test_static_lint_passes_on_every_ladder_but_the_two_designed_to_fail() -> None:
    """al10 and al12 are controls whose whole point is an unenforced sandwich, so they must fail
    the lint; every other ladder must pass it (LADDERS.md, batch summary)."""
    failing = {name for name in ladder_paths() if not make_ladder(name).lint().ok}
    assert failing == {"al10-skippable", "al12-unlearnable"}


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
