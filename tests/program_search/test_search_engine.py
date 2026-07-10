"""End-to-end: the bottom-up engine solving trivial tasks (sections 4-5)."""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.solvers.program_search.search.budget import Budget
from arc_lab.solvers.program_search.search.cost import ProgramSize
from arc_lab.solvers.program_search.search.search_engine import (
    BeamBottomUpSearchEngine,
    BottomUpSearchEngine,
)
from arc_lab.solvers.program_search.substrate.library import Library, Primitive
from arc_lab.solvers.program_search.substrate.program import Apply, Input
from arc_lab.solvers.program_search.substrate.types import GRID

_GRID = Grid.from_list([[1, 2], [3, 4]])


def _transpose(grid: Grid) -> Grid:
    return Grid.from_list([list(col) for col in zip(*grid.to_list(), strict=True)])


_TRANSPOSE = Primitive(name="transpose", param_types=(GRID,), return_type=GRID, impl=_transpose)
_EMPTY = Library(name="empty", primitives=())
_GEO = Library(name="geo", primitives=(_TRANSPOSE,))


def _bottom_up(max_depth: int) -> BottomUpSearchEngine:
    return BottomUpSearchEngine(
        constant_sources=(),
        function_hole_fill_mode="none",
        polymorphism_instantiation="monomorphize",
        budget=Budget(max_depth=max_depth, max_arity=1, max_pool=100),
    )


def test_solves_identity_with_the_input_leaf() -> None:
    task = Task(task_id="id", train=(Example(input=_GRID, output=_GRID),), test=())
    result = _bottom_up(max_depth=1).run(
        task=task, library=_EMPTY, constraints=(), cost=ProgramSize()
    )
    assert result.stats.solved
    assert result.ranked_programs == (Input(),)


def test_solves_a_single_primitive_composition() -> None:
    task = Task(task_id="t", train=(Example(input=_GRID, output=_transpose(_GRID)),), test=())
    result = _bottom_up(max_depth=2).run(
        task=task, library=_GEO, constraints=(), cost=ProgramSize()
    )
    assert result.stats.solved
    assert Apply(primitive="transpose", args=(Input(),)) in result.ranked_programs


def test_unsolvable_within_the_vocabulary_returns_nothing() -> None:
    task = Task(task_id="t", train=(Example(input=_GRID, output=_transpose(_GRID)),), test=())
    result = _bottom_up(max_depth=2).run(
        task=task, library=_EMPTY, constraints=(), cost=ProgramSize()
    )
    assert not result.stats.solved
    assert result.ranked_programs == ()


def _hconcat(*grids: Grid) -> Grid:
    rows: list[list[int]] = []
    for i in range(grids[0].height):
        row: list[int] = []
        for grid in grids:
            row.extend(grid.to_list()[i])
        rows.append(row)
    return Grid.from_list(rows)


_HCONCAT = Primitive(
    name="hconcat", param_types=(), return_type=GRID, variadic_param=GRID, impl=_hconcat
)


def test_solves_with_a_variadic_primitive() -> None:
    doubled = _hconcat(_GRID, _GRID)  # 2x4
    task = Task(task_id="v", train=(Example(input=_GRID, output=doubled),), test=())
    engine = BottomUpSearchEngine(
        constant_sources=(),
        function_hole_fill_mode="none",
        polymorphism_instantiation="monomorphize",
        budget=Budget(max_depth=2, max_arity=2, max_pool=100),
    )
    result = engine.run(
        task=task,
        library=Library(name="concat", primitives=(_HCONCAT,)),
        constraints=(),
        cost=ProgramSize(),
    )
    assert result.stats.solved
    assert Apply(primitive="hconcat", args=(Input(), Input())) in result.ranked_programs


def test_beam_engine_also_solves() -> None:
    task = Task(task_id="t", train=(Example(input=_GRID, output=_transpose(_GRID)),), test=())
    engine = BeamBottomUpSearchEngine(
        constant_sources=(),
        function_hole_fill_mode="none",
        polymorphism_instantiation="monomorphize",
        budget=Budget(max_depth=2, max_arity=1, max_pool=100),
        beam_width=50,
    )
    result = engine.run(task=task, library=_GEO, constraints=(), cost=ProgramSize())
    assert Apply(primitive="transpose", args=(Input(),)) in result.ranked_programs
