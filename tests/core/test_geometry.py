"""The addressing types: value semantics, the position/displacement split, and Rect's domain.

What is pinned here is what the search layer relies on. Above all **hashability by value** —
``search/signature.py`` uses runtime values as observational-equivalence pool keys, so a type with
identity semantics could not flow through a program at all.
"""

from __future__ import annotations

import pytest

from arc_lab.core.geometry import Coord, Offset, Rect


def test_addressing_values_are_hashable_and_compare_by_value() -> None:
    # The pool dedups on (type, signature); two separately-built coords naming the same cell must
    # be one key, not two.
    assert Coord(1, 2) == Coord(1, 2)
    assert hash(Coord(1, 2)) == hash(Coord(1, 2))
    assert len({Coord(1, 2), Coord(1, 2), Coord(2, 1)}) == 2
    assert len({Offset(0, 1), Offset(0, 1), Offset(1, 0)}) == 2
    assert len({Rect(Coord(0, 0), Offset(2, 2)), Rect(Coord(0, 0), Offset(2, 2))}) == 1


def test_a_coord_is_not_an_offset_even_with_the_same_components() -> None:
    # The whole point of the split: a position and a displacement are different things, so they
    # must not collapse into one pool entry either. (Typed as `object` because mypy --strict
    # rejects the comparison outright as non-overlapping -- which is the static half of this very
    # claim, and worth having both ways.)
    position: object = Coord(1, 2)
    displacement: object = Offset(1, 2)
    assert position != displacement
    assert len({Coord(1, 2), Offset(1, 2)}) == 2


def test_a_coord_may_be_negative_because_a_rect_may_hang_off_the_grid() -> None:
    # This is exactly what Mask structurally cannot represent, and why Rect exists.
    off_grid = Rect(Coord(-1, -2), Offset(3, 3))
    assert off_grid.origin == Coord(-1, -2)
    assert off_grid.height == 3 and off_grid.width == 3


def test_rect_reports_its_extent_as_height_width_and_area() -> None:
    rect = Rect(Coord(2, 5), Offset(3, 4))
    assert (rect.height, rect.width, rect.area) == (3, 4, 12)


@pytest.mark.parametrize("extent", [Offset(0, 2), Offset(2, 0), Offset(-1, 3)])
def test_a_degenerate_rect_raises_rather_than_being_empty(extent: Offset) -> None:
    # Matches Grid/Mask (both non-empty by construction), so a fully out-of-bounds `rect_clip` is a
    # domain error that prunes as ⊥ rather than a silent empty result.
    with pytest.raises(ValueError, match="extent must be positive"):
        Rect(Coord(0, 0), extent)


def test_they_are_immutable() -> None:
    with pytest.raises(AttributeError):
        Coord(0, 0).row = 5  # type: ignore[misc]
