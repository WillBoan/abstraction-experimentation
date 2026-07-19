"""``Budget.depth_limit``: the inclusive compositional-depth cap (leaf = 0)."""

from arc_lab.program_search.search.budget import Budget


def test_depth_limit_zero_is_leaves_only_not_exhausted() -> None:
    budget = Budget(depth_limit=0, max_arity=1, max_pool=10)
    assert not budget.exhausted  # generation 0 (the leaves) may still run
    assert budget.descend().exhausted  # a sub-search below leaves cannot


def test_descend_reduces_depth_limit_by_one() -> None:
    budget = Budget(depth_limit=3, max_arity=2, max_pool=100)
    assert budget.descend() == Budget(depth_limit=2, max_arity=2, max_pool=100)
    assert budget.depth_limit == 3  # descend does not mutate
