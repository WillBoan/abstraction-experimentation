"""The floor-breadth census: the WIDTH axis, computed statically (``ladders/breadth.py``).

The instrument that would have made the 2026-07-25 ``dae9d2b5`` diagnosis a one-second read. Its
whole value is that it fires BEFORE anything is searched, so these are fast tests over the
committed ladders -- no engine, no run.
"""

from __future__ import annotations

from arc_lab.program_search.ladders.breadth import RungBreadth
from arc_lab.program_search.ladders.registry import make_ladder


def _by_name(name: str) -> dict[str, RungBreadth]:
    return {entry.name: entry for entry in make_ladder(name).lint().breadth}


def test_the_census_catches_the_floor_that_cost_five_million() -> None:
    """`dae9d2b5-halves-union` is the calibration case. Neither rung takes a colour, but the floor
    carries `map_color`/`overlay`, so every rung is charged the full ten-colour battery -- and the
    round-1 width is two orders of magnitude above what the rung needs. THIS is the reading that
    was missing while the cost was being attributed to depth.

    ⚠ **The pinned width was 1,211 until 2026-07-27 and that number was wrong** -- and it is the
    number the batch's headline breadth findings were quoted in. `forecast_cost._slot_types`
    replicated a variadic primitive's LAST DECLARED parameter instead of its `variadic_param`, so
    `overlay : (Color, Grid...) -> Grid` was modelled as taking colour tuples (10 + 10^2 + 10^3 =
    1,110) rather than grids (30). Corrected against the engine on every uncompromised rung cell:
    21/42 exact before, 42/42 after (`experiments/2026-07-27-census-calibration/`). The tax on this
    floor is **131x**, not 1,211x; the diagnosis it drove is unchanged, its magnitude is not.
    """
    west = _by_name("dae9d2b5-halves-union")["west"]

    assert west.b1_min == 1  # the rung itself has essentially no width at round 1
    # EXACT, verified against the engine's own round-1 `composed` -- not a threshold.
    assert west.b1_full == 131
    ratio = west.ratio
    assert ratio is not None and ratio == 131.0

    colors = next(entry for entry in west.battery if entry.type_name == "color")
    assert (colors.minted, colors.used) == (10, 0)  # ten minted, none wanted
    assert colors.wasted == 10
    # ...and it names the primitives responsible, so the fix is obvious from the reading alone.
    assert set(colors.minted_because) >= {"map_color", "overlay"}


def test_a_rung_that_uses_a_constant_is_credited_for_it() -> None:
    """`east` = `crop_rect(g, nth(halves_h(g), 1))` -- one INT literal. The census must count it as
    USED, or "wasted battery" would blame every rung for the constants it does need."""
    east = _by_name("dae9d2b5-halves-union")["east"]
    ints = next(entry for entry in east.battery if entry.type_name == "int")
    assert ints.used == 1
    assert ints.minted > 1  # the floor still mints the whole 0..max-dim range


def test_a_lean_floor_reads_lean() -> None:
    """The contrast that makes the number meaningful. `al21-dag-siblings` has four Grid->Grid
    primitives and no constant battery at all, so its round-1 tax is single-digit -- the census
    separates "this floor is fat" from "this rung is deep"."""
    for entry in _by_name("al21-dag-siblings").values():
        assert entry.battery == ()  # no primitive mentions a scalar type: nothing to mint
        ratio = entry.ratio
        assert ratio is not None and ratio < 20


def test_the_four_corners_are_ordered_and_the_marginals_overlap() -> None:
    """`b1_min` is the floor of the four prunings and `b1_full` the ceiling, on every rung of every
    corpus-backed ladder. The overlap claim is the one worth pinning: dropping a primitive can also
    drop the type that made its constants mintable, so the two single-pruning taxes double-count
    and `full - min` is NOT their sum."""
    for name in ("dae9d2b5-halves-union", "al21-dag-siblings", "al1-mirror"):
        for entry in make_ladder(name).lint().breadth:
            corners = (entry.b1_primitive_pruned, entry.b1_constant_pruned)
            assert entry.b1_min <= min(corners), f"{name}/{entry.name}"
            assert entry.b1_full >= max(corners), f"{name}/{entry.name}"
            primitive_tax = entry.b1_full - entry.b1_primitive_pruned
            constant_tax = entry.b1_full - entry.b1_constant_pruned
            joint = entry.b1_full - entry.b1_min
            assert joint <= primitive_tax + constant_tax, f"{name}/{entry.name}"


def test_a_structural_lint_prices_nothing() -> None:
    """The battery is a function of grid size, so a corpus-less lint reports NO breadth rather than
    pricing against imaginary grids -- the same discipline as `skipped_checks`."""
    assert make_ladder("al21-dag-siblings").lint(corpus_backed=False).breadth == ()
