"""The observational-equivalence dedup ``Pool`` and its ``PoolEntry`` records."""

from __future__ import annotations

from arc_lab.solvers.program_search.search.pool import Pool
from arc_lab.solvers.program_search.substrate.program import Const
from arc_lab.solvers.program_search.substrate.types import COLOR, GRID, INT

_A = Const(value=1, value_type=COLOR)
_B = Const(value=2, value_type=COLOR)
_C = Const(value=3, value_type=COLOR)


def test_add_dedup_keeps_the_cheapest_witness() -> None:
    pool = Pool()
    assert pool.add_dedup(GRID, (1,), _A, 2.0) is True  # first witness
    assert pool.add_dedup(GRID, (1,), _B, 1.0) is True  # strictly cheaper replaces
    assert pool.add_dedup(GRID, (1,), _C, 3.0) is False  # costlier is deduplicated away
    (entry,) = pool.items_of_type(GRID)
    assert entry.program is _B
    assert entry.cost == 1.0
    assert entry.sig == (1,)


def test_equal_cost_does_not_replace() -> None:
    pool = Pool()
    pool.add_dedup(GRID, (1,), _A, 1.0)
    assert pool.add_dedup(GRID, (1,), _B, 1.0) is False  # not strictly cheaper
    (entry,) = pool.items_of_type(GRID)
    assert entry.program is _A


def test_distinct_signatures_coexist() -> None:
    pool = Pool()
    pool.add_dedup(GRID, (1,), _A, 1.0)
    pool.add_dedup(GRID, (2,), _B, 1.0)
    assert pool.size() == 2
    assert set(pool.of_type(GRID)) == {_A, _B}


def test_same_signature_different_type_are_separate_buckets() -> None:
    pool = Pool()
    pool.add_dedup(GRID, (1,), _A, 1.0)
    pool.add_dedup(INT, (1,), _B, 1.0)  # same signature, different type ⇒ distinct
    assert pool.size() == 2
    assert next(iter(pool.items_of_type(GRID))).program is _A
    assert next(iter(pool.items_of_type(INT))).program is _B


def test_missing_type_is_empty() -> None:
    pool = Pool()
    assert list(pool.of_type(GRID)) == []
    assert list(pool.items_of_type(GRID)) == []


def test_cheapest_keeps_globally_cheapest_rebucketed() -> None:
    pool = Pool()
    pool.add_dedup(GRID, (1,), _A, 3.0)
    pool.add_dedup(INT, (2,), _B, 1.0)
    pool.add_dedup(COLOR, (3,), _C, 2.0)
    cut = pool.cheapest(2)
    assert cut.size() == 2
    assert set(cut.ranked()) == {_B, _C}  # the two cheapest survive


def test_ranked_orders_whole_pool_by_cost() -> None:
    pool = Pool()
    pool.add_dedup(GRID, (1,), _A, 3.0)
    pool.add_dedup(INT, (2,), _B, 1.0)
    pool.add_dedup(COLOR, (3,), _C, 2.0)
    assert pool.ranked() == (_B, _C, _A)
