"""The primitive-promotion loop, run: reference impl vs decomposition, decided automatically.

The loop is `reference Primitive` + `decomposition as a Program template` ->
:func:`make_abstraction` -> :func:`observationally_equivalent_functions`. Nothing here is new
machinery; the point is that a floor-lowering claim ("this powerful primitive is really just these
simpler ones") becomes a *checked* fact instead of a plausible-looking rewrite, and stays checked.

Two results are recorded, and the negative one matters as much as the positive:

- ``retain_colors`` IS a composition of the existing mask algebra -> it should leave the floor.
- ``largest_filled_square`` is NOT decomposable over the current substrate at all, because nothing in
  it produces a *list of regions* to search over. That is the cfb2ce5a headline made concrete: the
  difficulty is perceptual, not compositional.
"""

from __future__ import annotations

from arc_lab.program_search.analysis.equivalence import observationally_equivalent_functions
from arc_lab.program_search.analysis.grids import exact_grids
from arc_lab.program_search.substrate.abstraction import make_abstraction
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.primitives.mask import MASK_PRIMITIVES
from arc_lab.program_search.substrate.primitives.tiles import RETAIN_COLORS
from arc_lab.program_search.substrate.program import Apply, Const, Param, Program
from arc_lab.program_search.substrate.registry import BASE_PRIMITIVES
from arc_lab.program_search.substrate.types import COLOR, GRID, TypeCon

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


def test_nothing_in_the_substrate_produces_a_list_of_regions() -> None:
    """Why ``largest_filled_square`` cannot be decomposed here — a tripwire, not a preference.

    Decomposing "the largest all-nonzero square" means enumerating candidate regions and selecting
    among them, which needs ``map``/``filter``/``sort_by``/``fold`` to have a ``list[mask]`` or
    ``list[grid]`` to range over. The substrate has no such producer: every list-valued primitive
    yields ``list[color]`` or a ``list`` of pairs. So the percept is irreducible *by construction*,
    and lowering that floor is a deliberate substrate extension (a region-enumeration tier), not a
    rewrite. When someone adds one, this test fails — which is the signal to revisit the decomposition.
    """
    region_lists = {
        name: prim.return_type
        for name, prim in BASE_PRIMITIVES.items()
        if isinstance(prim.return_type, TypeCon)
        and prim.return_type.name == "list"
        and prim.return_type.args in ((GRID,), (TypeCon("mask"),))
    }
    assert not region_lists, f"a region enumerator now exists: {region_lists}"
