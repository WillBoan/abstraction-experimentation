"""Short-circuit ``If`` branching: the node (§11.3) and its enumeration (§5.4) of ARCHITECTURE.md.

Branching is *summoned by the vocabulary*: the library's ``if`` capability token enables it, and the
enumerator composes dedicated short-circuit ``If`` nodes — never an eager ``Apply`` — so a branch
that errors outside its selected domain (domain-splitting ``if``) still yields a program that is
correct on unseen test inputs.
"""

from __future__ import annotations

import pytest

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.cost import ProgramSize
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.search.search_result import SearchResult
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.primitives.control import IF
from arc_lab.program_search.substrate.program import Apply, Const, If, Input, Program
from arc_lab.program_search.substrate.types import BOOL, COLOR, GRID

_WIDE = Grid.from_list([[1, 2, 3], [4, 5, 6]])  # 2x3
_TALL = Grid.from_list([[7, 8], [9, 0], [1, 2]])  # 3x2


def _transpose(grid: Grid) -> Grid:
    return Grid.from_list([list(col) for col in zip(*grid.to_list(), strict=True)])


def _is_wide(grid: Grid) -> bool:
    return grid.width > grid.height


def _wide_transpose(grid: Grid) -> Grid:
    """Transpose, but *only defined on wide grids* — a deliberately partial primitive."""
    if not _is_wide(grid):
        raise ValueError("wide_transpose is undefined on non-wide grids")
    return _transpose(grid)


_IS_WIDE = Primitive(name="is_wide", param_types=(GRID,), return_type=BOOL, impl=_is_wide)
_TRANSPOSE = Primitive(name="transpose", param_types=(GRID,), return_type=GRID, impl=_transpose)
_WIDE_TRANSPOSE = Primitive(
    name="wide_transpose", param_types=(GRID,), return_type=GRID, impl=_wide_transpose
)


# -- the If node (§11.3) -----------------------------------------------------------------------


def _boom(grid: Grid) -> Grid:
    raise RuntimeError("the unselected branch must never be evaluated")


_BOOM_LIB = Library(
    name="boom",
    primitives=(
        Primitive(name="boom", param_types=(GRID,), return_type=GRID, impl=_boom),
        _IS_WIDE,
    ),
)


def test_if_evaluates_only_the_selected_branch() -> None:
    program = If(
        cond=Apply(primitive="is_wide", args=(Input(),)),
        then=Input(),
        orelse=Apply(primitive="boom", args=(Input(),)),  # would raise if ever evaluated
    )
    assert program.evaluate(_WIDE, _BOOM_LIB) == _WIDE


def test_if_requires_a_boolean_condition() -> None:
    program = If(cond=Const(value=3, value_type=COLOR), then=Input(), orelse=Input())
    with pytest.raises(TypeError):
        program.evaluate(_WIDE, _BOOM_LIB)


def test_if_round_trips_through_serialization() -> None:
    program = If(
        cond=Apply(primitive="is_wide", args=(Input(),)),
        then=Apply(primitive="transpose", args=(Input(),)),
        orelse=Input(),
    )
    assert Program.from_dict(program.to_dict()) == program
    assert program.children() == (program.cond, program.then, program.orelse)


def test_the_if_token_is_never_executable() -> None:
    # The eager impl is retired: the token only *summons* branching; applying it is a loud error.
    with pytest.raises(RuntimeError):
        IF.impl(True, 1, 2)


# -- enumeration (§5.4): branching summoned by the bag -----------------------------------------

# Task: wide inputs are transposed, tall inputs pass through — unsolvable without branching.
_TASK = Task(
    task_id="branch",
    train=(
        Example(input=_WIDE, output=_transpose(_WIDE)),
        Example(input=_TALL, output=_TALL),
    ),
    test=(),
)


def _run(library: Library) -> SearchResult:
    engine = BottomUpSearchEngine(
        constant_sources=(),
        function_hole_fill_mode="none",
        polymorphism_instantiation="monomorphize",
        unpinned_type_var_mode="reject",
    )
    return engine.run(
        train_examples=_TASK.train,
        library=library,
        constraints=(),
        cost=ProgramSize(),
        budget=Budget(depth_limit=2, max_arity=1, max_pool=200),
    )


def test_total_branching_solves_with_the_if_token() -> None:
    result = _run(Library(name="branch", primitives=(IF, _IS_WIDE, _TRANSPOSE)))
    assert result.stats.solved
    expected = If(
        cond=Apply(primitive="is_wide", args=(Input(),)),
        then=Apply(primitive="transpose", args=(Input(),)),
        orelse=Input(),
    )
    assert expected in result.ranked_programs


def test_domain_splitting_if_composes_partial_branches() -> None:
    # wide_transpose errors on the tall training input (⊥ there), yet stays pooled as branch
    # scaffolding (§5.5/§5.6) and combines into a total solution.
    library = Library(name="split", primitives=(IF, _IS_WIDE, _WIDE_TRANSPOSE))
    result = _run(library)
    assert result.stats.solved
    solution = result.ranked_programs[0]
    # The §11.3 point: correct on *unseen* inputs of both regimes — the unselected (and there
    # undefined) branch is never evaluated.
    fresh_wide = Grid.from_list([[5, 6, 7, 8], [9, 0, 1, 2]])
    fresh_tall = Grid.from_list([[5], [6], [7]])
    assert solution.evaluate_grid(fresh_wide, library) == _transpose(fresh_wide)
    assert solution.evaluate_grid(fresh_tall, library) == fresh_tall


def test_branching_off_without_the_token() -> None:
    # Same task, same vocabulary minus the `if` entry: branching is off (Table A), unsolvable.
    result = _run(Library(name="no-if", primitives=(_IS_WIDE, _TRANSPOSE)))
    assert not result.stats.solved
    assert result.ranked_programs == ()
