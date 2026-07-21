"""Seed grids for hand-authoring (`arc-lab ladder-seeds`): the properties that make them usable."""

from __future__ import annotations

import pytest

from arc_lab.taskgen.ladders import seed_grids, symmetry_repair_seeds


def test_seed_grids_vary_within_and_across_variants() -> None:
    """The properties the lint's variation checks look for -- so pasted seeds pass by design."""
    first = seed_grids(3, rows=2, cols=3, variant=1)
    second = seed_grids(3, rows=2, cols=3, variant=2)
    assert len(set(first)) == 3  # distinct within a task
    assert not set(first) & set(second)  # and across tasks
    for grid in first:
        assert grid.shape == (2, 3)


def test_seed_grids_are_asymmetric_under_both_flips() -> None:
    """An identity/flip shortcut must not coincide with the intended solution."""
    for grid in seed_grids(4, rows=2, cols=3, variant=7):
        rows = grid.to_list()
        assert rows != [row[::-1] for row in rows]  # flip_h
        assert rows != rows[::-1]  # flip_v


def test_background_frames_the_grid() -> None:
    grid = seed_grids(1, rows=3, cols=3, variant=1, background=0)[0]
    rows = grid.to_list()
    assert rows[0] == [0, 0, 0] and rows[2] == [0, 0, 0]
    assert rows[1][0] == 0 and rows[1][2] == 0
    with pytest.raises(ValueError, match="rows and cols >= 3"):
        seed_grids(1, rows=2, cols=2, variant=1, background=0)


def test_symmetry_repair_seeds_carry_holes_needing_both_axes() -> None:
    grid = symmetry_repair_seeds(1, rows=3, cols=4, variant=1)[0]
    rows = grid.to_list()
    # The corner and both its mirrors are blank, so an H-repair alone cannot fill (0,0).
    assert rows[0][0] == 0 and rows[0][3] == 0 and rows[2][0] == 0
    assert rows[2][3] != 0  # its diagonal is kept -- that is what makes the V-repair recover it
