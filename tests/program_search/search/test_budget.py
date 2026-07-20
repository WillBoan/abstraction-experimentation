"""``Budget``: the inclusive compositional-depth cap (leaf = 0) and the two stop limits."""

from typing import Any

import pytest

from arc_lab.program_search.search.budget import Budget


def test_depth_limit_zero_is_leaves_only_not_exhausted() -> None:
    budget = Budget(depth_limit=0, max_arity=1, max_pool=10)
    assert not budget.exhausted  # generation 0 (the leaves) may still run
    assert budget.descend().exhausted  # a sub-search below leaves cannot


def test_descend_reduces_depth_limit_by_one() -> None:
    budget = Budget(depth_limit=3, max_arity=2, max_pool=100)
    assert budget.descend() == Budget(depth_limit=2, max_arity=2, max_pool=100)
    assert budget.depth_limit == 3  # descend does not mutate


def test_descend_preserves_the_stop_limits() -> None:
    """The stop limits are run-global, so a sub-search must not be handed a fresh allowance.

    Every field is set to a NON-default here on purpose: ``descend`` builds ``Budget``
    positionally, so a field it forgets silently reverts to its default, which a
    defaults-valued budget could never detect.
    """
    budget = Budget(
        depth_limit=3,
        max_arity=2,
        max_pool=100,
        considered_limit=500,
        considered_limit_mode="generation-end",
        solution_limit=7,
        solution_limit_mode="immediate",
    )
    descended = budget.descend()
    assert descended.considered_limit == 500
    assert descended.considered_limit_mode == "generation-end"
    assert descended.solution_limit == 7
    assert descended.solution_limit_mode == "immediate"
    assert descended.depth_limit == 2  # the one field that does change


def test_stop_limits_default_to_disabled() -> None:
    budget = Budget(depth_limit=1, max_arity=1, max_pool=10)
    assert budget.considered_limit is None
    assert budget.solution_limit is None
    assert budget.considered_limit_mode == "immediate"
    assert budget.solution_limit_mode == "generation-end"


@pytest.mark.parametrize("field", ["considered_limit", "solution_limit"])
@pytest.mark.parametrize("value", [0, -1, "garbage", 1.5])
def test_a_stop_limit_must_be_a_positive_int_or_none(field: str, value: Any) -> None:
    """Validated here, not in ``execution/overrides.py``: ``_coerce`` type-checks against the
    CURRENT value, which for an optional field at its default is ``None`` -- so it skips the check
    entirely and ``--set budget.considered_limit=garbage`` would otherwise install the string."""
    kwargs: dict[str, Any] = {field: value}
    with pytest.raises(ValueError, match=field):
        Budget(depth_limit=1, max_arity=1, max_pool=10, **kwargs)


@pytest.mark.parametrize("field", ["considered_limit_mode", "solution_limit_mode"])
def test_a_stop_mode_must_be_a_known_literal(field: str) -> None:
    kwargs: dict[str, Any] = {field: "eventually"}
    with pytest.raises(ValueError, match=field):
        Budget(depth_limit=1, max_arity=1, max_pool=10, **kwargs)
