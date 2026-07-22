"""The rung probe: what search actually retains, per rung, at design time."""

from __future__ import annotations

import dataclasses

import pytest

from arc_lab.core.grid import Grid
from arc_lab.program_search.ladders.probe import (
    AS_INTENDED,
    COLLAPSED,
    COLLISION,
    NO_SKIP,
    SKIP_PATH,
    MintProbe,
    RungProbe,
    _discriminating_grids,
    probe_ladder,
    probe_rung,
)
from arc_lab.program_search.ladders.registry import make_ladder


def test_a_sound_rung_probes_clean() -> None:
    # al1's r1 is the reference sound jump: both demos solve from L_0, search retains exactly the
    # intended program, nothing one level up is reachable, and sleep mints the rung at its arity.
    probe = probe_rung(make_ladder("al1-mirror"), 1)
    assert probe.ok and probe.findings() == ()
    assert [p.verdict for p in probe.wake] == [AS_INTENDED, AS_INTENDED]
    assert [p.verdict for p in probe.skip] == [NO_SKIP, NO_SKIP]
    assert probe.mint is not None and probe.mint.recovered and probe.mint.arity_matches


def test_probe_catches_al14s_literal_collapse() -> None:
    # The 2026-07-21 notebook's headline, reproduced automatically: r1 solves at depth 2, not the
    # 3 its template claims, because the free INT params are fixed within-task and enumerable.
    probe = probe_rung(make_ladder("al14-cell-row-grid"), 1)
    collapsed = [p for p in probe.wake if p.verdict == COLLAPSED]
    assert collapsed, [p.verdict for p in probe.wake]
    assert collapsed[0].found_depth == 2 and collapsed[0].intended_depth == 3
    assert not probe.ok


def test_probe_catches_a_skip_path() -> None:
    # al10 is the control whose top is deliberately reachable without the rung; the probe reports
    # it rung-locally, with the program that reaches it.
    probe = probe_rung(make_ladder("al10-skippable"), 1)
    assert [p.verdict for p in probe.skip] == [SKIP_PATH]
    assert probe.skip[0].found is not None
    assert not probe.skip_ok and not probe.ok


@pytest.mark.slow
def test_probe_separates_a_collision_from_a_collapse() -> None:
    # Both al14 demos retain a depth-2 program, but they fail differently: -00's is the same
    # function spelled cheaper (collapse), -01's reads a DIFFERENT cell and only fits because
    # al14's grids confound the two (collision). Needs a guard above the reference config's, which
    # censors -01 before it is found -- itself the 2026-07-21 finding that the guard was too small.
    spec = make_ladder("al14-cell-row-grid")
    budget = dataclasses.replace(spec.reference_config.budget, considered_limit=400_000)
    probe = probe_rung(spec, 1, budget=budget)
    verdicts = {p.task_id: p.verdict for p in probe.wake}
    assert verdicts == {"move_cell_up-00": COLLAPSED, "move_cell_up-01": COLLISION}
    # And sleep, fed what wake really retained, mints the wrong thing at the wrong arity.
    assert probe.mint is not None and not probe.mint.recovered
    assert probe.mint.minted_arity == 5 and probe.mint.intended_arity == 3


def test_discriminating_grids_separate_al14s_confounded_cells() -> None:
    # al14's own grids make read(g, 0, 2) == read(g, 2, 1) in ALL 16 of them, so corpus grids
    # alone cannot expose a program reading the wrong cell. The position-separating probes must.
    grids = _discriminating_grids({(4, 3)})
    assert any(g.to_list()[0][2] != g.to_list()[2][1] for g in grids)
    assert all(g.height == 4 and g.width == 3 for g in grids)


def test_discriminating_grids_are_deterministic() -> None:
    assert _discriminating_grids({(2, 3), (4, 3)}) == _discriminating_grids({(4, 3), (2, 3)})


def test_a_wrong_arity_mint_is_a_finding() -> None:
    # Recovering the behaviour but at a wider arity is not a pass: every extra parameter
    # multiplies the abstraction's cost at every use site (al14's 5-vs-3 mint was 289x).
    probe = RungProbe(
        level=1,
        name="r1",
        library="L0",
        wake=(),
        skip=(),
        mint=MintProbe(minted=("abs0",), recovered=True, minted_arity=5, intended_arity=3),
        forecast_ceiling=None,
    )
    assert not probe.mint_ok
    assert "minted at arity 5" in probe.findings()[0]


def test_probe_ladder_covers_every_rung_bottom_up() -> None:
    probes = probe_ladder(make_ladder("al1-mirror"))
    assert [p.level for p in probes] == [1, 2]
    assert [p.name for p in probes] == ["rot180", "mirror_recolor"]
    assert all(p.ok for p in probes)
    assert "as-intended" in probes[0].render()


def test_probe_grids_are_grids() -> None:
    assert all(isinstance(g, Grid) for g in _discriminating_grids({(3, 3)}))
