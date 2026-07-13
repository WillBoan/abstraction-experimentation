"""The core-contract supporting types: ``Scope`` (De Bruijn Γ), ``Context``, ``Budget``."""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.context import Context
from arc_lab.program_search.search.scope import Scope
from arc_lab.program_search.substrate.types import COLOR, INT

_GRID = Grid.from_list([[1, 2], [3, 4]])


# -- Scope: De Bruijn ordering (last extended = index 0) -----------------------


def test_empty_scope() -> None:
    assert len(Scope()) == 0
    assert len(Scope(())) == 0


def test_extend_appends_innermost_and_is_immutable() -> None:
    base = Scope()
    extended = base.extend(INT).extend(COLOR)
    assert len(extended) == 2
    assert len(base) == 0  # extend does not mutate
    assert extended.binders == (INT, COLOR)


def test_type_of_counts_from_innermost() -> None:
    scope = Scope().extend(INT).extend(COLOR)  # row=INT (outer), col=COLOR (inner)
    assert scope.type_of(0) == COLOR  # innermost = last extended = De Bruijn 0
    assert scope.type_of(1) == INT  # next one out


# -- Context -------------------------------------------------------------------


def test_context_defaults_to_empty_binding() -> None:
    ctx = Context(_GRID)
    assert ctx.input_grid is _GRID
    assert ctx.scope_binding == ()


def test_context_carries_scope_binding() -> None:
    ctx = Context(_GRID, (5, 7))  # (row, col)
    assert ctx.scope_binding == (5, 7)


# -- Budget --------------------------------------------------------------------


def test_budget_fields() -> None:
    budget = Budget(max_depth=3, max_arity=4, max_pool=100)
    assert (budget.max_depth, budget.max_arity, budget.max_pool) == (3, 4, 100)


def test_descend_decrements_depth_only_and_is_immutable() -> None:
    budget = Budget(max_depth=3, max_arity=4, max_pool=100)
    inner = budget.descend()
    assert inner == Budget(max_depth=2, max_arity=4, max_pool=100)
    assert budget.max_depth == 3  # descend does not mutate


def test_exhausted() -> None:
    assert not Budget(max_depth=1, max_arity=4, max_pool=100).exhausted
    assert Budget(max_depth=0, max_arity=4, max_pool=100).exhausted
    assert Budget(max_depth=1, max_arity=4, max_pool=100).descend().exhausted
