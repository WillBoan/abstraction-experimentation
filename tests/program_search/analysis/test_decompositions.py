"""The primitive-promotion loop, run: reference impl vs decomposition, decided automatically.

The loop is `reference Primitive` + `decomposition as a Program template` ->
:func:`make_abstraction` -> :func:`observationally_equivalent_functions`. Nothing here is new
machinery; the point is that a floor-lowering claim ("this powerful primitive is really just these
simpler ones") becomes a *checked* fact instead of a plausible-looking rewrite, and stays checked.

Results recorded so far:

- ``retain_colors`` IS a composition of the existing mask algebra -> it left the floor.
- ``largest_filled_square`` **was** irreducible, and no longer is. The original finding was that
  nothing in the substrate produced a *list of regions* to select among, so the percept could not be
  decomposed *by construction* -- pinned here as a tripwire that would fail the moment a producer
  appeared. The addressing tier (``primitives/regions.py``) is that producer, the tripwire fired as
  designed, and the percept is now ``crop_rect(g, head(filled_squares(g, bg)))`` at depth 3.

That arc is the point of the loop: a negative result with a *named structural cause* told us exactly
which capability to add, and the same check that proved it impossible now proves the decomposition
correct.
"""

from __future__ import annotations

from arc_lab.program_search.analysis.depth import compositional_depth
from arc_lab.program_search.analysis.equivalence import observationally_equivalent_functions
from arc_lab.program_search.analysis.grids import exact_grids
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.primitives.mask import MASK_PRIMITIVES
from arc_lab.program_search.substrate.primitives.tiles import RETAIN_COLORS
from arc_lab.program_search.substrate.program import Apply, Const, Param, Program
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import COLOR, COORD, GRID, INT, RECT, TypeCon

_MASK_ALGEBRA = Library("mask-algebra", MASK_PRIMITIVES)

#: ``retain_colors(g, c1, c2)`` == zero every cell outside the two selected colors. Depth 4.
#: An earlier attempt via ``overlay``/``filter_color`` was WRONG (``filter_color`` floods to the
#: most-common color, not 0, and ``overlay`` is a masked max) — hence the check rather than the eye.
_RETAIN_COLORS_DECOMPOSED: Program = Apply(
    "paint_through_mask",
    (
        Param(0, GRID),
        Apply(
            "mask_complement",
            (
                Apply(
                    "mask_union",
                    (
                        Apply("mask_by_color", (Param(0, GRID), Param(1, COLOR))),
                        Apply("mask_by_color", (Param(0, GRID), Param(2, COLOR))),
                    ),
                ),
            ),
        ),
        Const(0, COLOR),
    ),
)


def _decomposition(name: str, template: Program, reference: Primitive) -> Primitive:
    """The decomposition as a callable primitive, at the reference's exact signature."""
    return make_abstraction(
        name,
        template,
        _MASK_ALGEBRA,
        signature=(reference.param_types, reference.return_type),
    )


def test_retain_colors_is_exactly_the_mask_algebra_composition() -> None:
    # Every (grid, color, color) combo over the exact-mode battery: 4 shapes x the full 0-9 color
    # domain on both parameters. No split, so `retain_colors` earns no place on a floor.
    decomposed = _decomposition(
        "retain_colors_decomposed", _RETAIN_COLORS_DECOMPOSED, RETAIN_COLORS
    )
    verdict = observationally_equivalent_functions(
        RETAIN_COLORS,
        decomposed,
        exact_grids({(3, 3), (4, 4), (2, 5), (1, 1)}),
        max_combos=100_000,
    )
    assert verdict.equivalent, verdict.counterexample
    assert verdict.cases_tested > 2_000  # the whole battery ran; the combo cap did not truncate it


def test_the_loop_refutes_a_decomposition_that_is_merely_plausible() -> None:
    # The guard on the guard: dropping the complement keeps the *complement* of the intended cells,
    # which is a wrong-but-plausible rewrite. The loop must catch it, or it proves nothing above.
    plausible: Program = Apply(
        "paint_through_mask",
        (
            Param(0, GRID),
            Apply(
                "mask_union",
                (
                    Apply("mask_by_color", (Param(0, GRID), Param(1, COLOR))),
                    Apply("mask_by_color", (Param(0, GRID), Param(2, COLOR))),
                ),
            ),
            Const(0, COLOR),
        ),
    )
    verdict = observationally_equivalent_functions(
        RETAIN_COLORS, _decomposition("wrong", plausible, RETAIN_COLORS), exact_grids({(3, 3)})
    )
    assert not verdict.equivalent
    assert verdict.counterexample is not None


def test_the_substrate_can_now_enumerate_regions_to_select_among() -> None:
    """The capability whose absence made the percept irreducible.

    The predecessor of this test asserted that NO primitive produced a ``list[rect]``/``list[mask]``,
    so ``map``/``filter``/``sort_by``/``head`` had nothing region-shaped to range over. That was the
    named structural cause behind "cfb2ce5a's difficulty is perceptual, not compositional" — and the
    thing the addressing tier was built to fix.
    """
    producers = {
        name
        for name, prim in BASE_PRIMITIVES.items()
        if isinstance(prim.return_type, TypeCon)
        and prim.return_type.name == "list"
        and prim.return_type.args in ((RECT,), (TypeCon("mask"),), (COORD,))
    }
    assert {"filled_squares", "connected_regions", "quadrants", "content_coords"} <= producers


def test_largest_filled_square_is_no_longer_irreducible() -> None:
    """The headline: the percept that could not be decomposed at all is now a depth-3 composition.

    ``filled_squares`` orders largest-first then row-major, which is exactly the reference's
    documented tie-break (topmost, then leftmost) — so ``head`` of it IS the source square, and
    ``crop_rect`` is the generic elimination that used to be fused into the same atom.
    """
    library = Library(
        "addressing-tier",
        tuple(BASE_PRIMITIVES[name] for name in ("crop_rect", "head", "filled_squares")),
    )
    grid = Param(0, GRID)
    template: Program = Apply(
        "crop_rect",
        (grid, Apply("head", (Apply("filled_squares", (grid, Const(0, COLOR))),))),
    )
    assert compositional_depth(template) == 3

    decomposed = make_abstraction(
        "largest_filled_square_decomposed", template, library, signature=((GRID,), GRID)
    )
    verdict = observationally_equivalent_functions(
        BASE_PRIMITIVES["largest_filled_square"],
        decomposed,
        exact_grids({(1, 1), (2, 5), (3, 3), (4, 4), (5, 5), (6, 4)}),
        max_combos=100_000,
    )
    assert verdict.equivalent, verdict.counterexample
    assert verdict.cases_tested > 30


def test_the_background_is_a_parameter_so_the_general_reading_is_one_rung_higher() -> None:
    """Why ONE parameterized ``filled_squares`` beats two named primitives.

    The specialized reading is ``filled_squares(g, 0)`` (depth 1 — ``0`` is a COLOR constant leaf);
    the general one is ``filled_squares(g, most_common_color(g))`` (depth 2). Being one level apart
    is the whole point: a ladder can climb from the specialized percept to the general one as a real
    rung, which two unrelated atoms could never express.
    """
    grid = Param(0, GRID)
    specialized: Program = Apply("filled_squares", (grid, Const(0, COLOR)))
    general: Program = Apply("filled_squares", (grid, Apply("most_common_color", (grid,))))
    assert compositional_depth(specialized) == 1
    assert compositional_depth(general) == 2


def _addressing_lib(*names: str) -> Library:
    return Library("addressing", tuple(BASE_PRIMITIVES[name] for name in names))


def test_relative_tile_decomposes_into_the_addressing_algebra() -> None:
    """The second bespoke atom to fall: ``relative_tile(g, down, right)`` located the source square
    and cropped the tile ``down``/``right`` whole squares away -- two jobs fused. Over the tier it is
    the source square (``head(filled_squares)``), a lattice step (``offset(mul(...), mul(...))`` --
    per-axis, so not ``offset_scale``), and the generic ``crop_rect``. Depth 9: a lot of composition,
    which is the honest measure of how much this atom was doing.
    """
    grid, down, right = Param(0, GRID), Param(1, INT), Param(2, INT)
    square = Apply("head", (Apply("filled_squares", (grid, Const(0, COLOR))),))
    size = Apply("offset_row", (Apply("rect_extent", (square,)),))
    step = Apply("offset", (Apply("mul", (down, size)), Apply("mul", (right, size))))
    tile = Apply(
        "rect",
        (
            Apply("coord_add", (Apply("rect_origin", (square,)), step)),
            Apply("rect_extent", (square,)),
        ),
    )
    template: Program = Apply("crop_rect", (grid, tile))
    library = _addressing_lib(
        "head",
        "filled_squares",
        "offset_row",
        "rect_extent",
        "offset",
        "mul",
        "rect",
        "coord_add",
        "rect_origin",
        "crop_rect",
    )
    decomposed = make_abstraction(
        "relative_tile_decomposed", template, library, signature=((GRID, INT, INT), GRID)
    )
    verdict = observationally_equivalent_functions(
        BASE_PRIMITIVES["relative_tile"],
        decomposed,
        exact_grids({(2, 2), (4, 4), (4, 6), (5, 5), (6, 6)}),
        max_combos=50_000,
    )
    assert verdict.equivalent, verdict.counterexample
    assert verdict.cases_tested > 500


def test_nth_nonzero_color_is_not_a_clean_composition_because_it_totalizes() -> None:
    """A refusal that is a finding, not a failure. The core of ``nth_nonzero_color(g, i)`` is
    ``read`` at the i-th ``content_coords`` position -- but the reference returns color 0 when i is
    out of range (it TOTALIZES), while ``nth`` raises. So exact equivalence correctly splits, and
    names the witness: an index past the last nonzero cell. Retiring this atom needs the guard made
    explicit (an ``if`` over ``length``), not just the read -- which is exactly what the loop tells us.
    """
    grid, index = Param(0, GRID), Param(1, INT)
    coords = Apply("content_coords", (grid, Const(0, COLOR)))
    at = Apply("nth", (coords, index))
    core: Program = Apply("read", (grid, Apply("coord_row", (at,)), Apply("coord_col", (at,))))
    library = _addressing_lib("read", "coord_row", "coord_col", "nth", "content_coords")
    decomposed = make_abstraction(
        "nth_nonzero_color_core", core, library, signature=((GRID, INT), COLOR)
    )
    verdict = observationally_equivalent_functions(
        BASE_PRIMITIVES["nth_nonzero_color"], decomposed, exact_grids({(2, 2), (3, 3)})
    )
    assert not verdict.equivalent
    assert verdict.counterexample is not None  # (grid, index-past-the-end)
