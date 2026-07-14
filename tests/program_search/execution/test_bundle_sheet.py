"""The candidate bundle sheet: every entry resolves, and a representative spread of known
coherent/incoherent outcomes match ``_PRIMITIVE_BUNDLES2.md``'s own framing."""

from __future__ import annotations

import pytest

from arc_lab.program_search.execution.bundle_sheet import BUNDLES, resolve_bundle
from arc_lab.program_search.execution.check_coherence import check_library_coherence
from arc_lab.program_search.execution.presets import resolve_library


def test_every_bundle_resolves_and_reports_without_raising() -> None:
    """A smoke/integrity test: every primitive name in the sheet is real (catches typos)."""
    for name in BUNDLES:
        library, constant_sources = resolve_bundle(name)
        report = check_library_coherence(library, constant_sources=constant_sources)
        assert report.library_name == name


def test_unknown_bundle_fails_loudly_with_known_names() -> None:
    with pytest.raises(KeyError, match="unknown bundle"):
        resolve_bundle("NOPE")


@pytest.mark.parametrize(
    "name",
    [
        "FLOOR",
        "FLOOR_AFFINE",
        "FLOOR_DIV",
        "UNIVERSAL_FLOOR",
        "SYMMETRY",
        "MASK_BASIC",
        "MASK_MIN",
        "HO_RECOLOR",
    ],
)
def test_floors_are_coherent(name: str) -> None:
    library, constant_sources = resolve_bundle(name)
    report = check_library_coherence(library, constant_sources=constant_sources)
    assert report.is_coherent, report.findings
    assert report.goal_directed


def test_floor_progression_needs_no_constant_sources() -> None:
    """The doc's deliberate "Const: none" fact for the FLOOR ladder: nothing here is minted, only
    derived from grid dimensions — losing that assumption in the sheet would silently mask it."""
    for name in ("FLOOR", "FLOOR_AFFINE", "FLOOR_DIV"):
        _, constant_sources = resolve_bundle(name)
        assert constant_sources == ()


@pytest.mark.parametrize(
    "name",
    [
        "ARITH_BASIC",
        "ARITH_DIV",
        "ARITH_FN",
        "IF",
        "BOOL_LOGIC",
        "BOOL_CMP",
        "CTRL",
        "PAIR",
        "PERCEIVE_COLOR",
        "PERCEIVE_INT",
        "MASK_INTRO",
    ],
)
def test_value_only_fragments_are_never_goal_directed_alone(name: str) -> None:
    """Pure Int/BOOL/Pair/Color/Mask fragments never reach Grid by themselves — internally closed
    (or not) is orthogonal to producing the type ARC actually needs."""
    library, constant_sources = resolve_bundle(name)
    report = check_library_coherence(library, constant_sources=constant_sources)
    assert not report.goal_directed
    assert not report.is_coherent


def test_list_ops_is_an_island_without_an_on_off_ramp() -> None:
    library, constant_sources = resolve_bundle("LIST_OPS")
    report = check_library_coherence(library, constant_sources=constant_sources)
    assert not report.is_coherent
    assert set(report.dead_primitives) == {"zip", "length", "head"}


def test_ho_basic_is_dead_without_a_list_producer() -> None:
    """``map``/``filter``/``fold``/``sort_by`` alone: the ``list[a]`` sibling is never produced —
    all four are type-closure islands, not just thin hole-fills."""
    library, constant_sources = resolve_bundle("HO_BASIC")
    report = check_library_coherence(library, constant_sources=constant_sources)
    assert not report.is_coherent
    assert set(report.dead_primitives) == {"map", "filter", "fold", "sort_by"}


def test_cell_io_and_scale_are_coherent_once_a_reasonable_constant_policy_is_assumed() -> None:
    """Both fragments genuinely reach Grid (``set_cell``/``from_cells``/``scale``) — they only look
    broken under the conservative ``constant_sources=()`` default; the sheet's own default
    (``finite-enumerate``) reflects that they're meant to be paired with *some* constant policy."""
    for name in ("CELL_IO", "SCALE"):
        library, constant_sources = resolve_bundle(name)
        report = check_library_coherence(library, constant_sources=constant_sources)
        assert report.is_coherent, (name, report.findings)
        assert report.goal_directed


def test_ho_grid_alone_is_type_reachable_but_thin() -> None:
    """``build_grid`` alone: with a seeded Color leaf its body can trivially emit a constant, so
    it's not a hard island — but with no coordinate/comparison vocabulary it's flagged thin."""
    library, constant_sources = resolve_bundle("HO_GRID")
    report = check_library_coherence(library, constant_sources=constant_sources)
    assert report.is_coherent  # a warning, not an error
    hole_fill = [f for f in report.findings if f.check == "hole-fill"]
    assert len(hole_fill) == 1
    assert hole_fill[0].severity == "warning"


def test_resolve_library_falls_back_to_the_bundle_sheet() -> None:
    """``resolve_library`` (presets.py) resolves a bundle-sheet name directly, so
    `check-library-coherence FLOOR` needs no --primitives and no registration in LIBRARIES."""
    library = resolve_library("FLOOR")
    assert library.name == "FLOOR"
    assert {p.name for p in library.primitives} == {"read", "build_grid", "width", "height", "sub"}
