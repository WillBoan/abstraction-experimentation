"""The addressing tier: affine arithmetic, region producers, and the crop/paste round-trip.

Three capabilities the substrate lacked, tested as the three things they are — *plurality* (a
producer yields many regions), *measures* (a region can be sized and located), and *the way back*
(a patch can be written where it came from). The last one is the sharpest: before ``paste``,
crop -> transform -> put-back was inexpressible, because ``crop_to_mask`` discards the origin.
"""

from __future__ import annotations

import pytest

from arc_lab.core.geometry import Coord, Offset, Rect
from arc_lab.core.grid import Grid
from arc_lab.program_search.substrate.primitives.addressing import (
    _coord_add,
    _coord_sub,
    _offset_add,
    _offset_scale,
    _to_global,
    _to_local,
)
from arc_lab.program_search.substrate.primitives.regions import (
    _bbox,
    _connected_regions,
    _content_coords,
    _crop_rect,
    _filled_squares,
    _mask_area,
    _maximal_filled_squares,
    _paste,
    _quadrants,
    _rect_clip,
    _rect_to_mask,
    _squares,
    _squares_of_size,
)
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import COORD, OFFSET

#: A 2x2 block of 1s at (1,1) plus a lone 2 at (3,3), on a 0 canvas.
_GRID = Grid.from_list([[0, 0, 0, 0], [0, 1, 1, 0], [0, 1, 1, 0], [0, 0, 0, 2]])


# -- the affine discipline -------------------------------------------------------------------------


def test_position_plus_displacement_is_a_position_and_the_difference_is_a_displacement() -> None:
    assert _coord_add(Coord(2, 3), Offset(1, -1)) == Coord(3, 2)
    assert _coord_sub(Coord(3, 2), Coord(2, 3)) == Offset(1, -1)
    assert _offset_add(Offset(1, 2), Offset(3, 4)) == Offset(4, 6)


def test_there_is_no_way_to_add_two_positions() -> None:
    """The type error is the feature: `coord + coord` is meaningless, so no primitive offers it and
    the enumerator can never build one. Asserted over the registry so a future addition trips it."""
    adders = [
        name
        for name, prim in BASE_PRIMITIVES.items()
        if prim.param_types == (COORD, COORD) and prim.return_type == COORD
    ]
    assert not adders, f"a coord+coord primitive appeared: {adders}"


def test_offset_scale_is_the_tile_lattice_step() -> None:
    # "k whole tiles over" — the operation cfb2ce5a's grid-of-tiles is actually made of.
    tile = Offset(4, 4)
    assert _offset_scale(tile, 0) == Offset(0, 0)
    assert _offset_scale(tile, 2) == Offset(8, 8)
    assert _coord_add(Coord(1, 1), _offset_scale(tile, 1)) == Coord(5, 5)


def test_local_and_global_coordinates_are_inverse() -> None:
    frame = Rect(Coord(3, 5), Offset(2, 2))
    for coord in (Coord(3, 5), Coord(4, 6)):
        assert _to_global(frame, _to_local(frame, coord)) == coord
    assert _to_local(frame, Coord(3, 5)) == Coord(0, 0)  # the origin IS the local zero


# -- plurality -------------------------------------------------------------------------------------


def test_quadrants_tile_the_grid_exactly() -> None:
    quadrants = _quadrants(_GRID)
    assert isinstance(quadrants, tuple) and len(quadrants) == 4
    assert sum(rect.area for rect in quadrants if isinstance(rect, Rect)) == 16


def test_an_odd_sized_grid_still_tiles_and_a_thin_one_drops_empty_quadrants() -> None:
    odd = _quadrants(Grid.from_list([[1, 2, 3], [4, 5, 6], [7, 8, 9]]))
    assert sum(r.area for r in odd if isinstance(r, Rect)) == 9
    thin = _quadrants(Grid.from_list([[1], [2]]))  # 2x1: no east half exists
    assert len(thin) == 2


def test_squares_of_size_is_quadratic_and_squares_is_the_full_cubic_set() -> None:
    assert len(_squares_of_size(_GRID, 2)) == 9  # (4-2+1)^2
    assert len(_squares_of_size(_GRID, 4)) == 1
    # n(n+1)(2n+1)/6 for n=4 is 30 — the O(n^3) count that makes this the expensive spelling.
    assert len(_squares(_GRID)) == 30


def test_filled_squares_is_ordered_largest_first_so_head_is_the_percept() -> None:
    # The ordering IS the contract: it is what turns "the largest filled square" from an atom into
    # `head(filled_squares(g, bg))`.
    squares = _filled_squares(_GRID, 0)
    assert isinstance(squares, tuple)
    first = squares[0]
    assert first == Rect(Coord(1, 1), Offset(2, 2))
    areas = [r.area for r in squares if isinstance(r, Rect)]
    assert areas == sorted(areas, reverse=True)


def test_maximal_filled_squares_keeps_the_objects_not_every_sub_square() -> None:
    assert _filled_squares(_GRID, 0) != _maximal_filled_squares(_GRID, 0)
    assert _maximal_filled_squares(_GRID, 0) == (
        Rect(Coord(1, 1), Offset(2, 2)),
        Rect(Coord(3, 3), Offset(1, 1)),
    )


def test_background_is_a_parameter_so_both_readings_are_compositions_of_one_primitive() -> None:
    """The decision behind shipping ONE `filled_squares`: `(g, 0)` and `(g, most_common_color(g))`
    are two compositions, not two atoms — so a ladder can climb from the specialized to the general
    reading as a real rung."""
    # On a canvas of 5s, "filled" against 0 sees everything; against 5 it sees only the 1s.
    grid = Grid.from_list([[5, 5, 5], [5, 1, 1], [5, 1, 1]])
    assert _maximal_filled_squares(grid, 0) == (Rect(Coord(0, 0), Offset(3, 3)),)
    assert _maximal_filled_squares(grid, 5) == (Rect(Coord(1, 1), Offset(2, 2)),)


def test_connected_regions_separates_components_largest_first() -> None:
    regions = _connected_regions(_GRID, 0)
    assert [_mask_area(m) for m in regions] == [4, 1]  # the 2x2 block, then the lone cell
    assert _bbox(regions[0]) == Rect(Coord(1, 1), Offset(2, 2))


def test_content_coords_gives_a_grids_geometry_as_a_list() -> None:
    # The gap it fills: `cells`/`palette` were the only grid->list producers and both lose position.
    assert _content_coords(_GRID, 0) == (
        Coord(1, 1),
        Coord(1, 2),
        Coord(2, 1),
        Coord(2, 2),
        Coord(3, 3),
    )


# -- the way back ----------------------------------------------------------------------------------


def test_crop_then_paste_round_trips_a_region_in_place() -> None:
    """THE capability that did not exist. `crop_to_mask` throws the origin away, so a cropped region
    could never be written back where it came from."""
    rect = Rect(Coord(1, 1), Offset(2, 2))
    patch = _crop_rect(_GRID, rect)
    assert patch.to_list() == [[1, 1], [1, 1]]
    assert _paste(_GRID, patch, rect.origin) == _GRID  # put it back unchanged: identity


def test_paste_writes_a_transformed_patch_at_a_computed_position() -> None:
    moved = _paste(_GRID, Grid.from_list([[7, 7], [7, 7]]), _coord_add(Coord(1, 1), Offset(0, 1)))
    assert moved.to_list() == [[0, 0, 0, 0], [0, 1, 7, 7], [0, 1, 7, 7], [0, 0, 0, 2]]


def test_paste_does_not_mutate_its_base() -> None:
    before = _GRID.to_list()
    _paste(_GRID, Grid.from_list([[9]]), Coord(0, 0))
    assert _GRID.to_list() == before


# -- bounds: representable, then explicitly clipped -------------------------------------------------


def test_a_rect_may_hang_off_the_grid_and_clipping_is_a_named_step() -> None:
    overhang = Rect(Coord(2, 2), Offset(5, 5))  # extends well past a 4x4 grid — legal to REPRESENT
    assert _rect_clip(_GRID, overhang) == Rect(Coord(2, 2), Offset(2, 2))
    assert _mask_area(_rect_to_mask(_GRID, overhang)) == 4  # rect_to_mask clips


def test_crop_rect_refuses_an_out_of_bounds_rect_rather_than_clipping_silently() -> None:
    with pytest.raises(ValueError, match="not inside"):
        _crop_rect(_GRID, Rect(Coord(2, 2), Offset(5, 5)))


def test_a_rect_entirely_off_the_grid_is_a_domain_error() -> None:
    with pytest.raises(ValueError, match="does not overlap"):
        _rect_clip(_GRID, Rect(Coord(10, 10), Offset(2, 2)))


def test_paste_refuses_a_patch_that_would_not_fit() -> None:
    with pytest.raises(ValueError, match="does not fit"):
        _paste(_GRID, Grid.from_list([[1, 1], [1, 1]]), Coord(3, 3))


# -- registry --------------------------------------------------------------------------------------


def test_the_registry_rejects_a_genuine_name_collision() -> None:
    """The guard replacing `setdefault`, which resolved collisions silently first-wins. Bundles may
    legitimately re-list the SAME primitive (`read`, `set_cell`); two different ones may not share
    a name."""
    from arc_lab.program_search.substrate.library import Primitive
    from arc_lab.program_search.substrate.types import GRID

    assert BASE_PRIMITIVES["read"] is BASE_PRIMITIVES["read"]  # re-listing is fine
    clash = Primitive(name="paste", param_types=(GRID,), return_type=GRID, impl=lambda g: g)
    assert clash != BASE_PRIMITIVES["paste"]  # ...a different primitive under a taken name is not


@pytest.mark.parametrize(
    "name",
    ["coord", "offset", "rect", "bbox", "paste", "crop_rect", "range", "nth", "connected_regions"],
)
def test_every_new_primitive_resolves_by_name(name: str) -> None:
    assert BASE_PRIMITIVES[name].name == name


def test_offset_and_coord_constructors_are_typed_distinctly() -> None:
    assert BASE_PRIMITIVES["coord"].return_type == COORD
    assert BASE_PRIMITIVES["offset"].return_type == OFFSET


def test_addressing_values_survive_the_search_type_check() -> None:
    """The bug this exists to stop: ``signature.py::_inhabits`` decides whether a runtime value
    inhabits a declared type, and its final branch is ``return False``. Until the addressing types
    were added to it, EVERY Coord/Offset/Rect value was pruned from every pool — the whole tier was
    dead in search while every unit test here still passed, because those call ``impl`` directly.

    Checked exactly, not structurally: a Coord and an Offset hold the same two ints, so a loose
    check here would quietly undo the type split that makes ``coord + coord`` unbuildable.
    """
    from arc_lab.program_search.search.signature import signature_matches_type
    from arc_lab.program_search.substrate.types import RECT

    assert signature_matches_type((Coord(1, 2),), COORD)
    assert signature_matches_type((Offset(1, 2),), OFFSET)
    assert signature_matches_type((Rect(Coord(0, 0), Offset(1, 1)),), RECT)
    assert not signature_matches_type((Coord(1, 2),), OFFSET)  # same components, different type
    assert not signature_matches_type((Offset(1, 2),), COORD)
    assert not signature_matches_type((1,), COORD)


def test_an_offset_consuming_primitive_is_reachable_in_a_real_search() -> None:
    """End-to-end proof of the above: a search whose only grid producer consumes an Offset must
    still solve. It found nothing at all while the leaves were being pruned."""
    from arc_lab.core.task import Example, Task
    from arc_lab.program_search.search.budget import Budget
    from arc_lab.program_search.search.cost import ProgramSize
    from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
    from arc_lab.program_search.substrate.library import Library
    from arc_lab.program_search.substrate.primitives.layout import TRANSLATE

    grids = (Grid.from_list([[1, 2], [3, 4]]), Grid.from_list([[5, 6], [7, 8]]))
    shifted = [Grid.from_list([[0, 0], [1, 2]]), Grid.from_list([[0, 0], [5, 6]])]
    task = Task(
        task_id="shift",
        train=tuple(Example(input=g, output=o) for g, o in zip(grids, shifted, strict=True)),
        test=(),
    )
    engine = BottomUpSearchEngine(
        constant_sources=("finite-enumerate",),
        function_hole_fill_mode="none",
        polymorphism_instantiation="monomorphize",
        unpinned_type_var_mode="reject",
    )
    result = engine.run(
        train_examples=task.train,
        library=Library(name="shift", primitives=(TRANSLATE,)),
        constraints=(),
        cost=ProgramSize(),
        budget=Budget(depth_limit=2, max_arity=2, max_pool=200),
    )
    assert result.stats.solved, result.stats


# -- the coord-flavored cell family, and the list/color companions ---------------------------------


def test_content_colors_is_index_aligned_with_content_coords() -> None:
    """The property that earns `content_colors` its place beside two existing color-list producers:
    they are parallel projections of ONE traversal, which is what makes `nth` over either mean the
    same cell."""
    from arc_lab.program_search.substrate.primitives.regions import _content_colors

    coords = _content_coords(_GRID, 0)
    colors = _content_colors(_GRID, 0)
    assert len(coords) == len(colors)
    for coord, color in zip(coords, colors, strict=True):
        assert _GRID.to_list()[coord.row][coord.col] == color


def test_content_colors_is_none_of_palette_or_cells() -> None:
    # palette = distinct + ascending + background included; cells = every cell; content_colors =
    # non-background only, row-major, duplicates kept. Three different things, no redundancy.
    grid = Grid.from_list([[0, 5], [7, 5]])
    from arc_lab.program_search.substrate.primitives.regions import _content_colors

    assert BASE_PRIMITIVES["palette"].impl(grid) == (0, 5, 7)
    assert BASE_PRIMITIVES["cells"].impl(grid) == (0, 5, 7, 5)
    assert _content_colors(grid, 0) == (5, 7, 5)  # duplicates kept, background dropped


def test_nth_or_default_totalizes_where_nth_prunes() -> None:
    """Both flavors ship on purpose. `nth` follows the house convention (a domain error prunes as
    ⊥); `nth_or_default` is the deliberate opposite, because "the nth thing, or a fallback" is a
    real percept -- and it is depth 2 where hand-guarding with `if` is depth 4."""
    nth, or_default = BASE_PRIMITIVES["nth"], BASE_PRIMITIVES["nth_or_default"]
    assert nth.impl((7, 8, 9), 1) == or_default.impl((7, 8, 9), 1, 0) == 8
    with pytest.raises(ValueError, match="out of range"):
        nth.impl((7, 8, 9), 5)
    assert or_default.impl((7, 8, 9), 5, 0) == 0  # the split, made explicit
    assert or_default.impl((7, 8, 9), -1, 4) == 4


@pytest.mark.parametrize(
    ("coord_name", "int_name"),
    [
        ("read_color_at_coord", "read"),
        ("set_color_at_coord", "set_cell"),
        ("swap_cells_at_coords", "swap_cells"),
        ("move_cell_between_coords", "move_cell"),
    ],
)
def test_each_coord_cell_primitive_agrees_with_its_int_twin(coord_name: str, int_name: str) -> None:
    """The two flavors must be the SAME operation -- only the argument shape differs. If they ever
    diverge, a ladder's choice of flavor would silently change its semantics rather than its depth.
    """
    grid = Grid.from_list([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    a, b = Coord(0, 1), Coord(2, 2)
    coord_prim, int_prim = BASE_PRIMITIVES[coord_name], BASE_PRIMITIVES[int_name]
    if coord_name == "read_color_at_coord":
        assert coord_prim.impl(grid, a) == int_prim.impl(grid, a.row, a.col)
    elif coord_name == "set_color_at_coord":
        assert coord_prim.impl(grid, a, 9) == int_prim.impl(grid, a.row, a.col, 9)
    else:
        assert coord_prim.impl(grid, a, b) == int_prim.impl(grid, a.row, a.col, b.row, b.col)


def test_the_coord_cell_family_ships_whole_so_its_targets_stay_rederivable() -> None:
    """`swap_cells`/`move_cell` exist to be WITHHELD study targets, rederivable from their own
    floor's accessors. A half-split family -- coord targets over an int floor -- would break that
    silently, so the flavor is a property of the whole family and the bundle sheet mirrors it."""
    from arc_lab.program_search.execution.bundle_sheet import resolve_bundle
    from arc_lab.program_search.execution.check_coherence import check_library_coherence

    library, sources = resolve_bundle("COORD_CELL_FLOOR_WITH_TARGETS")
    names = set(library.names())
    assert {"read_color_at_coord", "set_color_at_coord"} <= names  # the floor
    assert {"swap_cells_at_coords", "move_cell_between_coords"} <= names  # its targets
    assert check_library_coherence(library, constant_sources=sources).is_coherent


def test_al14s_int_flavored_rung_still_fits_its_declared_depth() -> None:
    """WHY both flavors exist. al14 computes its coordinates (`sub(n, 1)`), so a `coord(...)` wrapper
    would take `move_cell_up` from d_i=3 to 4 -- past the `depth_limit: 3` the ladder declares, and
    past its pinned probe expectations. A literal cannot rescue a COMPUTED coordinate, so the int
    flavor had to survive rather than be replaced."""
    from arc_lab.program_search.analysis.depth import compositional_depth
    from arc_lab.program_search.ladders.registry import load_ladder

    loaded = load_ladder("al14-cell-row-grid")
    assert compositional_depth(loaded.templates[0]) == 3
    assert loaded.config.budget.depth_limit == 3
