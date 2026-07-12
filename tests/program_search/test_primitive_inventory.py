"""The slice-6 primitive inventory: impl-level behaviour, documented ⊥ cases, registry round-trip,
and a few engine-reach tests proving the new vocabulary composes in real (tiny) searches."""

from __future__ import annotations

import pytest

from arc_lab.core.grid import Grid
from arc_lab.core.mask import Mask
from arc_lab.core.task import Example, Task
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.cost import ProgramSize
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.arithmetic import (
    ABS,
    ARITHMETIC_PRIMITIVES,
    FLOORDIV,
    MAX,
    MIN,
    MOD,
)
from arc_lab.program_search.substrate.primitives.cells import MOVE_CELL, SWAP_CELLS
from arc_lab.program_search.substrate.primitives.color import FILTER_COLOR, SWAP_COLORS
from arc_lab.program_search.substrate.primitives.layout import (
    BLANK,
    CONCAT_H,
    CONCAT_V,
    DOWNSAMPLE,
    LAYOUT_PRIMITIVES,
    PAD,
    TILE_REPEAT,
    TRANSLATE,
)
from arc_lab.program_search.substrate.primitives.lists import HEAD, LENGTH, LIST_PRIMITIVES, ZIP
from arc_lab.program_search.substrate.primitives.mask import (
    BBOX_MASK,
    CROP_TO_CONTENT,
    CROP_TO_MASK,
    MASK_BY_COLOR,
    MASK_COMPLEMENT,
    MASK_DIFFERENCE,
    MASK_INTERSECT,
    MASK_PRIMITIVES,
    MASK_UNION,
    NONBG_MASK,
    PAINT_THROUGH_MASK,
)
from arc_lab.program_search.substrate.primitives.pairs import FST, PAIR, PAIR_PRIMITIVES, SND
from arc_lab.program_search.substrate.primitives.perceive import (
    COUNT_COLOR,
    LEAST_COMMON_COLOR,
    MOST_COMMON_COLOR,
    NUM_COLORS,
    PALETTE,
    PERCEIVE_PRIMITIVES,
    SHAPE,
)
from arc_lab.program_search.substrate.registry import resolve_primitive
from arc_lab.program_search.substrate.store import library_hash

# 0 dominates; one 3, two 5s; colors {0, 3, 5}.
_G = Grid.from_list([[0, 0, 3], [0, 5, 5]])


# -- perceivers -------------------------------------------------------------------------------------


def test_most_common_color() -> None:
    assert MOST_COMMON_COLOR.impl(_G) == 0


def test_most_common_color_tie_breaks_to_lowest() -> None:
    assert MOST_COMMON_COLOR.impl(Grid.from_list([[7, 2], [2, 7]])) == 2


def test_least_common_color_ignores_absent_colors() -> None:
    assert LEAST_COMMON_COLOR.impl(_G) == 3  # count 1; absent colors don't win with count 0


def test_least_common_color_tie_breaks_to_lowest() -> None:
    assert LEAST_COMMON_COLOR.impl(Grid.from_list([[7, 2], [2, 7]])) == 2


def test_count_color_and_num_colors() -> None:
    assert COUNT_COLOR.impl(_G, 5) == 2
    assert COUNT_COLOR.impl(_G, 9) == 0
    assert NUM_COLORS.impl(_G) == 3


def test_palette_is_ascending_presence_set() -> None:
    assert PALETTE.impl(_G) == (0, 3, 5)


def test_shape_is_a_height_width_pair() -> None:
    assert SHAPE.impl(_G) == (2, 3)


# -- palette transforms -----------------------------------------------------------------------------


def test_swap_colors_exchanges_both_directions() -> None:
    swapped = SWAP_COLORS.impl(Grid.from_list([[1, 2, 1]]), 1, 2)
    assert swapped == Grid.from_list([[2, 1, 2]])


def test_filter_color_floods_the_rest_to_most_common() -> None:
    assert FILTER_COLOR.impl(_G, 5) == Grid.from_list([[0, 0, 0], [0, 5, 5]])


# -- pairs & lists ----------------------------------------------------------------------------------


def test_pair_fst_snd_round_trip() -> None:
    assert PAIR.impl(1, 5) == (1, 5)
    assert FST.impl((1, 5)) == 1
    assert SND.impl((1, 5)) == 5


def test_fst_rejects_a_non_pair() -> None:
    with pytest.raises(TypeError):
        FST.impl((1, 2, 3))


def test_zip_pairs_elementwise_and_is_strict() -> None:
    assert ZIP.impl((1, 2), (5, 6)) == ((1, 5), (2, 6))
    with pytest.raises(ValueError):
        ZIP.impl((1, 2), (5,))


def test_length_and_head() -> None:
    assert LENGTH.impl((7, 8, 9)) == 3
    assert LENGTH.impl(()) == 0
    assert HEAD.impl((7, 8)) == 7
    with pytest.raises(ValueError):
        HEAD.impl(())


# -- arithmetic -------------------------------------------------------------------------------------


def test_arithmetic_extras() -> None:
    assert MIN.impl(2, 5) == 2 and MAX.impl(2, 5) == 5
    assert ABS.impl(-3) == 3
    assert FLOORDIV.impl(7, 2) == 3 and MOD.impl(7, 2) == 1


def test_zero_divisor_raises() -> None:
    with pytest.raises(ZeroDivisionError):
        FLOORDIV.impl(1, 0)
    with pytest.raises(ZeroDivisionError):
        MOD.impl(1, 0)


# -- cell transforms (the re-derivation targets) -----------------------------------------------------


def test_swap_cells_exchanges_two_cells() -> None:
    assert SWAP_CELLS.impl(Grid.from_list([[1, 2]]), 0, 0, 0, 1) == Grid.from_list([[2, 1]])


def test_move_cell_relocates_and_clears_to_zero() -> None:
    assert MOVE_CELL.impl(Grid.from_list([[7, 2]]), 0, 0, 0, 1) == Grid.from_list([[0, 7]])


def test_swap_cells_out_of_bounds_raises() -> None:
    with pytest.raises(IndexError):
        SWAP_CELLS.impl(Grid.from_list([[1]]), 0, 0, 5, 5)


# -- masks ------------------------------------------------------------------------------------------


def test_mask_by_color_and_nonbg_agree_here() -> None:
    by_five = MASK_BY_COLOR.impl(_G, 5)
    assert by_five == Mask.from_list([[0, 0, 0], [0, 1, 1]])
    assert NONBG_MASK.impl(_G) == Mask.from_list([[0, 0, 1], [0, 1, 1]])


def test_bbox_mask_fills_the_content_box() -> None:
    assert BBOX_MASK.impl(_G) == Mask.from_list([[0, 1, 1], [0, 1, 1]])


def test_bbox_mask_of_a_uniform_grid_raises() -> None:
    with pytest.raises(ValueError):
        BBOX_MASK.impl(Grid.from_list([[4, 4]]))


def test_mask_set_algebra() -> None:
    a = Mask.from_list([[1, 1, 0]])
    b = Mask.from_list([[0, 1, 1]])
    assert MASK_UNION.impl(a, b) == Mask.from_list([[1, 1, 1]])
    assert MASK_INTERSECT.impl(a, b) == Mask.from_list([[0, 1, 0]])
    assert MASK_DIFFERENCE.impl(a, b) == Mask.from_list([[1, 0, 0]])
    assert MASK_COMPLEMENT.impl(a) == Mask.from_list([[0, 0, 1]])


def test_mask_set_algebra_shape_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        MASK_UNION.impl(Mask.from_list([[1]]), Mask.from_list([[1, 0]]))


def test_crop_to_mask_takes_the_whole_bbox_rectangle() -> None:
    mask = Mask.from_list([[0, 0, 0], [0, 1, 1]])
    assert CROP_TO_MASK.impl(_G, mask) == Grid.from_list([[5, 5]])
    diagonal = Mask.from_list([[0, 1, 0], [0, 0, 1]])  # bbox spans both rows, cols 1-2
    assert CROP_TO_MASK.impl(_G, diagonal) == Grid.from_list([[0, 3], [5, 5]])


def test_crop_to_mask_empty_or_mismatched_raises() -> None:
    with pytest.raises(ValueError):
        CROP_TO_MASK.impl(_G, Mask.from_list([[0, 0, 0], [0, 0, 0]]))
    with pytest.raises(ValueError):
        CROP_TO_MASK.impl(_G, Mask.from_list([[1]]))


def test_paint_through_mask_recolors_only_selected_cells() -> None:
    mask = Mask.from_list([[1, 0, 0], [0, 0, 1]])
    assert PAINT_THROUGH_MASK.impl(_G, mask, 9) == Grid.from_list([[9, 0, 3], [0, 5, 9]])


def test_crop_to_content() -> None:
    assert CROP_TO_CONTENT.impl(_G) == Grid.from_list([[0, 3], [5, 5]])
    with pytest.raises(ValueError):
        CROP_TO_CONTENT.impl(Grid.from_list([[4, 4]]))


# -- layout -----------------------------------------------------------------------------------------


def test_blank_and_its_bounds() -> None:
    assert BLANK.impl(2, 2, 7) == Grid.from_list([[7, 7], [7, 7]])
    with pytest.raises(ValueError):
        BLANK.impl(0, 2, 7)
    with pytest.raises(ValueError):
        BLANK.impl(31, 2, 7)


def test_translate_shifts_and_fills_with_zero() -> None:
    assert TRANSLATE.impl(Grid.from_list([[1, 2], [3, 4]]), 1, 0) == Grid.from_list([[0, 0], [1, 2]])
    assert TRANSLATE.impl(Grid.from_list([[1, 2]]), 0, -1) == Grid.from_list([[2, 0]])
    assert TRANSLATE.impl(Grid.from_list([[1]]), 5, 5) == Grid.from_list([[0]])  # shifted fully out


def test_concat_h_and_v() -> None:
    assert CONCAT_H.impl(Grid.from_list([[1]]), Grid.from_list([[2]])) == Grid.from_list([[1, 2]])
    assert CONCAT_V.impl(Grid.from_list([[1]]), Grid.from_list([[2]])) == Grid.from_list([[1], [2]])
    with pytest.raises(ValueError):
        CONCAT_H.impl(Grid.from_list([[1]]), Grid.from_list([[1], [2]]))
    with pytest.raises(ValueError):
        CONCAT_V.impl(Grid.from_list([[1]]), Grid.from_list([[1, 2]]))


def test_concat_over_the_size_cap_is_a_no_op() -> None:
    wide = Grid.from_list([[1] * 20])
    assert CONCAT_H.impl(wide, wide) == wide


def test_pad_and_its_no_op_cases() -> None:
    assert PAD.impl(Grid.from_list([[5]]), 1, 0) == Grid.from_list([[0, 0, 0], [0, 5, 0], [0, 0, 0]])
    small = Grid.from_list([[5]])
    assert PAD.impl(small, 0, 0) == small  # thickness < 1: no-op
    assert PAD.impl(small, 15, 0) == small  # would exceed the cap: no-op


def test_tile_repeat_and_its_no_op_cases() -> None:
    assert TILE_REPEAT.impl(Grid.from_list([[1, 2]]), 2, 2) == Grid.from_list(
        [[1, 2, 1, 2], [1, 2, 1, 2]]
    )
    grid = Grid.from_list([[1, 2]])
    assert TILE_REPEAT.impl(grid, 0, 2) == grid  # non-positive factor: no-op
    assert TILE_REPEAT.impl(grid, 1, 16) == grid  # 32 wide would exceed the cap: no-op


def test_downsample_is_stride_sampling() -> None:
    scaled = Grid.from_list([[1, 1, 2, 2], [1, 1, 2, 2]])
    assert DOWNSAMPLE.impl(scaled, 2) == Grid.from_list([[1, 2]])
    with pytest.raises(ValueError):
        DOWNSAMPLE.impl(scaled, 0)


# -- registry & serde round-trip --------------------------------------------------------------------

_ALL_NEW = (
    *PERCEIVE_PRIMITIVES,
    SWAP_COLORS,
    FILTER_COLOR,
    *PAIR_PRIMITIVES,
    *LIST_PRIMITIVES,
    *ARITHMETIC_PRIMITIVES,
    *MASK_PRIMITIVES,
    SWAP_CELLS,
    MOVE_CELL,
    *LAYOUT_PRIMITIVES,
)


def test_every_new_primitive_is_registered() -> None:
    for primitive in _ALL_NEW:
        assert resolve_primitive(primitive.name) is primitive


def test_a_library_of_all_new_primitives_round_trips() -> None:
    library = Library(name="slice6", primitives=_ALL_NEW)
    restored = Library.from_dict(library.to_dict())
    assert restored == library
    assert library_hash(restored) == library_hash(library)


# -- engine reach: the new vocabulary composes in real searches --------------------------------------


def _engine(**overrides: object) -> BottomUpSearchEngine:
    defaults: dict[str, object] = {
        "constant_sources": ("finite-enumerate",),
        "function_hole_fill_mode": "none",
        "polymorphism_instantiation": "monomorphize",
        "unpinned_type_var_mode": "reject",
    }
    defaults.update(overrides)
    return BottomUpSearchEngine(**defaults)  # type: ignore[arg-type]


def _solve(task: Task, library: Library, max_depth: int) -> object:
    engine = _engine()
    result = engine.run(
        train_examples=task.train,
        library=library,
        constraints=(),
        cost=ProgramSize(),
        budget=Budget(max_depth=max_depth, max_arity=2, max_pool=200),
    )
    assert result.stats.solved, result.stats
    return result.ranked_programs[0]


def test_recolor_background_solves_via_a_perceiver() -> None:
    # map_color(g, most_common_color(g), c) — the perceive→transform shape: the source color is
    # *derived*, so one program covers training grids with different backgrounds.
    def recolor_bg(grid: Grid) -> Grid:
        return Grid.from_list(
            [[9 if c == MOST_COMMON_COLOR.impl(grid) else c for c in row] for row in grid.to_list()]
        )

    grids = (Grid.from_list([[0, 0, 3]]), Grid.from_list([[5, 5, 1]]))  # different backgrounds
    task = Task(
        task_id="recolor-bg",
        train=tuple(Example(input=g, output=recolor_bg(g)) for g in grids),
        test=(),
    )
    from arc_lab.program_search.substrate.primitives.color import MAP_COLOR

    library = Library(name="rbg", primitives=(MAP_COLOR, MOST_COMMON_COLOR))
    solution = _solve(task, library, max_depth=3)
    unseen = Grid.from_list([[2, 2, 0]])
    assert solution.evaluate_grid(unseen, library) == recolor_bg(unseen)  # type: ignore[attr-defined]


def test_crop_to_content_solves_a_crop_task() -> None:
    task = Task(
        task_id="crop",
        train=(
            Example(input=Grid.from_list([[0, 0], [0, 7]]), output=Grid.from_list([[7]])),
            Example(input=Grid.from_list([[0, 3, 2], [0, 0, 0]]), output=Grid.from_list([[3, 2]])),
        ),
        test=(),
    )
    library = Library(name="crop", primitives=(CROP_TO_CONTENT,))
    _solve(task, library, max_depth=2)


def test_pair_composition_pools_and_projects() -> None:
    # snd(shape(g)) == width — a pair value flowing through composition, ending in an INT the goal
    # test can't use directly, so drive it through blank: blank(1, snd(shape(g)), 0) = a 1 x width
    # zero row, size-generally.
    def one_by_width(grid: Grid) -> Grid:
        return Grid.from_list([[0] * grid.width])

    grids = (Grid.from_list([[1, 2, 3]]), Grid.from_list([[4, 4]]))
    task = Task(
        task_id="row",
        train=tuple(Example(input=g, output=one_by_width(g)) for g in grids),
        test=(),
    )
    library = Library(name="row", primitives=(SHAPE, SND, BLANK))
    solution = _solve(task, library, max_depth=4)
    unseen = Grid.from_list([[9, 9, 9, 9]])
    assert solution.evaluate_grid(unseen, library) == one_by_width(unseen)  # type: ignore[attr-defined]
