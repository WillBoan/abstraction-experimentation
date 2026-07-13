"""The ``Mask`` value type: validation, value semantics, and its type-system wiring."""

from __future__ import annotations

import pytest

from arc_lab.core.grid import Grid
from arc_lab.core.mask import Mask
from arc_lab.program_search.search.pool import Pool
from arc_lab.program_search.search.signature import signature_matches_type
from arc_lab.program_search.substrate.program import Const, Input
from arc_lab.program_search.substrate.types import MASK, base_type

# -- construction & validation ---------------------------------------------------------------------


def test_mask_from_list_and_back() -> None:
    mask = Mask.from_list([[True, False], [False, True]])
    assert mask.to_list() == [[True, False], [False, True]]
    assert mask.shape == (2, 2)
    assert mask.height == 2 and mask.width == 2
    assert mask[0, 0] is True and mask[0, 1] is False


def test_mask_accepts_zero_one_ints() -> None:
    assert Mask.from_list([[1, 0]]).to_list() == [[True, False]]


def test_mask_rejects_non_2d() -> None:
    with pytest.raises(ValueError, match="2-D"):
        Mask([True, False])


def test_mask_rejects_empty() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        Mask([[]])


def test_mask_backing_array_is_frozen_and_array_property_is_a_copy() -> None:
    mask = Mask.from_list([[True]])
    copy = mask.array
    copy[0, 0] = False
    assert mask[0, 0] is True  # mutation of the copy does not reach the mask


# -- value semantics --------------------------------------------------------------------------------


def test_masks_are_hashable_and_compared_by_value() -> None:
    a = Mask.from_list([[True, False]])
    b = Mask.from_list([[True, False]])
    c = Mask.from_list([[False, True]])
    assert a == b and hash(a) == hash(b)
    assert a != c
    assert a != Grid.from_list([[1, 0]])  # never equal to a Grid, even with matching cells


def test_equal_masks_dedup_in_a_pool_unequal_dont() -> None:
    pool = Pool()
    a = Mask.from_list([[True]])
    b = Mask.from_list([[True]])
    c = Mask.from_list([[False]])
    assert pool.add_dedup(MASK, (a,), Input(), cost=1.0).inserted
    assert not pool.add_dedup(MASK, (b,), Const(value=0, value_type=MASK), cost=2.0).inserted  # deduped
    assert pool.add_dedup(MASK, (c,), Const(value=1, value_type=MASK), cost=2.0).inserted  # distinct: kept
    assert len(list(pool.items_of_type(MASK))) == 2


# -- type-system wiring -----------------------------------------------------------------------------


def test_inhabits_accepts_a_mask_for_mask_and_rejects_others() -> None:
    mask = Mask.from_list([[True]])
    assert signature_matches_type((mask,), MASK)
    assert not signature_matches_type((Grid.from_list([[1]]),), MASK)
    assert not signature_matches_type((1,), MASK)
    assert not signature_matches_type((mask,), base_type("grid"))


def test_mask_base_type_round_trips_by_name() -> None:
    assert base_type("mask") is MASK
