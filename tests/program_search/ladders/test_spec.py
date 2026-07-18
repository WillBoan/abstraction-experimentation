"""``LadderSpec`` + ``lint()`` on ladder #1 (``al1-mirror``): the verified tractability sandwich."""

from __future__ import annotations

import dataclasses

from arc_lab.program_search.ladders.registry import make_ladder


def test_ladder1_lints_ok_with_the_verified_sandwich() -> None:
    shape = make_ladder("al1-mirror").lint()
    assert shape.ok
    assert shape.height == 3
    assert shape.validity_window == (3, 3)
    assert shape.raw_depth_profile == (4,)
    by_name = {rung.name: rung for rung in shape.rungs}
    assert by_name["rot180"].jump_depth == 2
    assert by_name["rot180"].double_jump_depth == 3  # mirror_recolor inlined over L0 (skip rot180)
    assert by_name["rot180"].fan_in == 0  # rot180 uses only floor primitives
    assert by_name["mirror_recolor"].jump_depth == 2
    assert by_name["mirror_recolor"].double_jump_depth is None  # the last bridging rung
    assert by_name["mirror_recolor"].fan_in == 1  # references rot180 once


def test_oracle_chain_grows_by_one_rung_per_level() -> None:
    spec = make_ladder("al1-mirror")
    assert "rot180" not in spec.floor()
    assert "rot180" in spec.oracle_library(1)
    assert "mirror_recolor" not in spec.oracle_library(1)
    assert "mirror_recolor" in spec.oracle_library(2)


def test_rung_tasks_resolve_from_demonstration_ids() -> None:
    spec = make_ladder("al1-mirror")
    rot180_ids = {t.task.task_id for t in spec.rung_tasks(1)}
    assert rot180_ids == {"rot180-00", "rot180-01"}


def test_render_marks_ok_and_lists_the_rungs() -> None:
    text = make_ladder("al1-mirror").render()
    assert "al1-mirror" in text and "OK" in text and "rot180" in text and "mirror_recolor" in text


def test_lint_catches_a_budget_that_makes_the_raw_top_reachable() -> None:
    # A budget deep enough to reach the raw top (d_raw=4) breaks the raw-intractable claim.
    spec = make_ladder("al1-mirror")
    deep = dataclasses.replace(spec.reference_config.budget, max_depth=6)
    bad = dataclasses.replace(spec, reference_config=spec.reference_config.with_(budget=deep))
    shape = bad.lint()
    assert not shape.ok
    assert any(finding.check == "raw-intractable" and not finding.ok for finding in shape.findings)
