"""The cfb2ce5a reference primitives: the documented tie-breaks, the degenerate cases, and ⊥.

These are scaffolding meant to be decomposed away (``primitives/tiles.py``), so what is pinned here
is exactly what a decomposition would have to reproduce — above all the tie-break rules, which are
the part a plausible-looking replacement gets silently wrong.
"""

from __future__ import annotations

import pytest

from arc_lab.core.grid import Grid
from arc_lab.program_search.substrate.primitives.tiles import (
    _largest_filled_square,
    _nth_nonzero_color,
    _nth_seed_source_color,
    _relative_tile,
    _retain_colors,
    _square_origin,
    _write_relative_tile,
)
from arc_lab.program_search.substrate.registry import resolve_primitive


def test_the_largest_square_wins_over_an_earlier_smaller_one() -> None:
    # A 2x2 sits above-left of a 3x3: size dominates position, so the 3x3 is the source square.
    grid = Grid.from_list(
        [
            [1, 1, 0, 0, 0],
            [1, 1, 0, 0, 0],
            [0, 0, 2, 2, 2],
            [0, 0, 2, 2, 2],
            [0, 0, 2, 2, 2],
        ]
    )
    assert _square_origin(grid) == (2, 2, 3)
    assert _largest_filled_square(grid) == Grid.from_list([[2, 2, 2], [2, 2, 2], [2, 2, 2]])


def test_equal_sized_squares_break_topmost_then_leftmost() -> None:
    # Three 2x2s. Row 0 beats row 2 (topmost); within row 0, col 0 beats col 3 (leftmost).
    grid = Grid.from_list(
        [
            [1, 1, 0, 2, 2],
            [1, 1, 0, 2, 2],
            [0, 0, 0, 0, 0],
            [3, 3, 0, 0, 0],
            [3, 3, 0, 0, 0],
        ]
    )
    assert _square_origin(grid) == (0, 0, 2)


def test_a_lone_nonzero_cell_is_a_1x1_square_and_an_empty_grid_is_bottom() -> None:
    assert _square_origin(Grid.from_list([[0, 0], [0, 7]])) == (1, 1, 1)
    with pytest.raises(ValueError, match="no filled square"):
        _square_origin(Grid.from_list([[0, 0], [0, 0]]))


def test_relative_tile_steps_by_whole_source_squares_and_falls_off_as_bottom() -> None:
    grid = Grid.from_list(
        [
            [1, 1, 2, 2],
            [1, 1, 3, 3],
            [4, 4, 0, 0],
            [4, 4, 0, 0],
        ]
    )
    assert _square_origin(grid) == (0, 0, 2)
    assert _relative_tile(grid, 0, 0) == Grid.from_list([[1, 1], [1, 1]])
    assert _relative_tile(grid, 0, 1) == Grid.from_list([[2, 2], [3, 3]])
    assert _relative_tile(grid, 1, 0) == Grid.from_list([[4, 4], [4, 4]])
    with pytest.raises(ValueError, match="outside"):  # off the grid: prunes as ⊥, no no-op
        _relative_tile(grid, 2, 0)


def test_nth_nonzero_color_reads_row_major_and_returns_0_past_the_end() -> None:
    grid = Grid.from_list([[0, 5], [7, 0]])
    assert _nth_nonzero_color(grid, 0) == 5  # row-major: (0,1) precedes (1,0)
    assert _nth_nonzero_color(grid, 1) == 7
    assert _nth_nonzero_color(grid, 2) == 0  # absent -> 0, not ⊥
    assert _nth_nonzero_color(grid, -1) == 0


def test_nth_seed_source_color_reads_the_pattern_under_the_nth_seed() -> None:
    pattern = Grid.from_list([[2, 1], [1, 2]])
    seeds = Grid.from_list([[0, 8], [3, 0]])
    # Seeds row-major: (0,1) then (1,0); the pattern holds 1 and 1 beneath them.
    assert _nth_seed_source_color(pattern, seeds, 0) == 1
    assert _nth_seed_source_color(pattern, seeds, 1) == 1
    # A tile with fewer seeds than the ladder reads degenerates to 0 (an identity recolor), not ⊥.
    assert _nth_seed_source_color(pattern, seeds, 2) == 0
    with pytest.raises(ValueError, match="aligned"):
        _nth_seed_source_color(pattern, Grid.from_list([[0]]), 0)


def test_retain_colors_keeps_exactly_the_two_named_colors() -> None:
    grid = Grid.from_list([[1, 2, 3], [4, 1, 2]])
    assert _retain_colors(grid, 1, 2) == Grid.from_list([[1, 2, 0], [0, 1, 2]])
    assert _retain_colors(grid, 5, 6) == Grid.from_list([[0, 0, 0], [0, 0, 0]])


def test_write_relative_tile_overwrites_the_whole_target_tile() -> None:
    base = Grid.from_list(
        [
            [1, 1, 0, 0],
            [1, 1, 0, 9],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
        ]
    )
    tile = Grid.from_list([[5, 5], [5, 5]])
    # The seed (the 9) is inside the target tile and is overwritten, as cfb2ce5a requires.
    assert _write_relative_tile(base, base, tile, 0, 1) == Grid.from_list(
        [
            [1, 1, 5, 5],
            [1, 1, 5, 5],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
        ]
    )
    with pytest.raises(ValueError, match="does not match"):
        _write_relative_tile(base, base, Grid.from_list([[5]]), 0, 1)


def test_write_relative_tile_does_not_mutate_its_base() -> None:
    # `Grid.array` hands back a writable copy; a primitive that forgot that would corrupt the caller's
    # grid, and every downstream signature with it.
    base = Grid.from_list([[1, 1, 0, 0], [1, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]])
    before = base.to_list()
    _write_relative_tile(base, base, Grid.from_list([[5, 5], [5, 5]]), 0, 1)
    assert base.to_list() == before


@pytest.mark.parametrize(
    "name",
    [
        "largest_filled_square",
        "relative_tile",
        "nth_nonzero_color",
        "nth_seed_source_color",
        "retain_colors",
        "write_relative_tile",
    ],
)
def test_every_tile_primitive_resolves_by_name(name: str) -> None:
    # Registry membership is what lets a `.ladder` floor name them; without it the cohort cannot load.
    assert resolve_primitive(name).name == name
