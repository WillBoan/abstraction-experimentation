"""End-to-end: the bottom-up engine solving trivial tasks (sections 4-5)."""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.cost import ProgramSize
from arc_lab.program_search.search.polymorphism import PolymorphismInstantiation
from arc_lab.program_search.search.search_engine import (
    BeamBottomUpSearchEngine,
    BottomUpSearchEngine,
)
from arc_lab.program_search.substrate.library import (
    Library,
    Primitive,
    Value,
    apply_function_value,
)
from arc_lab.program_search.substrate.program import Apply, Input, PrimRef
from arc_lab.program_search.substrate.types import GRID, ArrowType

_GRID = Grid.from_list([[1, 2], [3, 4]])


def _transpose(grid: Grid) -> Grid:
    return Grid.from_list([list(col) for col in zip(*grid.to_list(), strict=True)])


_TRANSPOSE = Primitive(name="transpose", param_types=(GRID,), return_type=GRID, impl=_transpose)
_EMPTY = Library(name="empty", primitives=())
_GEO = Library(name="geo", primitives=(_TRANSPOSE,))

# One engine, many budgets: the budget is per-run data, not engine machinery.
_ENGINE = BottomUpSearchEngine(
    constant_sources=(),
    function_hole_fill_mode="none",
    polymorphism_instantiation="monomorphize",
    unpinned_type_var_mode="reject",
)


def _budget(max_depth: int, max_arity: int = 1) -> Budget:
    return Budget(max_depth=max_depth, max_arity=max_arity, max_pool=100)


def test_solves_identity_with_the_input_leaf() -> None:
    task = Task(task_id="id", train=(Example(input=_GRID, output=_GRID),), test=())
    result = _ENGINE.run(
        train_examples=task.train,
        library=_EMPTY,
        constraints=(),
        cost=ProgramSize(),
        budget=_budget(max_depth=1),
    )
    assert result.stats.solved
    assert result.ranked_programs == (Input(),)


def test_solves_a_single_primitive_composition() -> None:
    task = Task(task_id="t", train=(Example(input=_GRID, output=_transpose(_GRID)),), test=())
    result = _ENGINE.run(
        train_examples=task.train,
        library=_GEO,
        constraints=(),
        cost=ProgramSize(),
        budget=_budget(max_depth=2),
    )
    assert result.stats.solved
    assert Apply(primitive="transpose", args=(Input(),)) in result.ranked_programs


def test_unsolvable_within_the_vocabulary_returns_nothing() -> None:
    task = Task(task_id="t", train=(Example(input=_GRID, output=_transpose(_GRID)),), test=())
    result = _ENGINE.run(
        train_examples=task.train,
        library=_EMPTY,
        constraints=(),
        cost=ProgramSize(),
        budget=_budget(max_depth=2),
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
    result = _ENGINE.run(
        train_examples=task.train,
        library=Library(name="concat", primitives=(_HCONCAT,)),
        constraints=(),
        cost=ProgramSize(),
        budget=_budget(max_depth=2, max_arity=2),
    )
    assert result.stats.solved
    assert Apply(primitive="hconcat", args=(Input(), Input())) in result.ranked_programs


def test_solves_under_every_polymorphism_policy() -> None:
    task = Task(task_id="t", train=(Example(input=_GRID, output=_transpose(_GRID)),), test=())
    policies: tuple[PolymorphismInstantiation, ...] = ("monomorphize", "bounded", "unrestricted")
    for policy in policies:
        engine = BottomUpSearchEngine(
            constant_sources=(),
            function_hole_fill_mode="none",
            polymorphism_instantiation=policy,
            unpinned_type_var_mode="reject",
        )
        result = engine.run(
            train_examples=task.train,
            library=_GEO,
            constraints=(),
            cost=ProgramSize(),
            budget=_budget(max_depth=2),
        )
        assert Apply(primitive="transpose", args=(Input(),)) in result.ranked_programs


def _rot90(grid: Grid) -> Grid:
    return Grid.from_list([list(row) for row in zip(*grid.to_list()[::-1], strict=True)])


_ROT90 = Primitive(name="rot90", param_types=(GRID,), return_type=GRID, impl=_rot90)


def _twice_impl(f: Value, g: Grid) -> Value:
    once = apply_function_value(f, (g,))
    return apply_function_value(f, (once,))


# twice(f, g) = f(f(g)) — a genuine higher-order primitive: the function is applied internally.
_TWICE = Primitive(
    name="twice",
    param_types=(ArrowType((GRID,), GRID), GRID),
    return_type=GRID,
    impl=_twice_impl,
)


def test_point_free_higher_order_fill_via_a_primref() -> None:
    # target = rot180 = rot90 applied twice; within depth 2 the only solution is twice(&rot90, Input).
    rot180 = _rot90(_rot90(_GRID))
    task = Task(task_id="ho", train=(Example(input=_GRID, output=rot180),), test=())
    engine = BottomUpSearchEngine(
        constant_sources=(),
        function_hole_fill_mode="point-free",
        polymorphism_instantiation="monomorphize",
        unpinned_type_var_mode="reject",
    )
    result = engine.run(
        train_examples=task.train,
        library=Library(name="ho", primitives=(_TWICE, _ROT90)),
        constraints=(),
        cost=ProgramSize(),
        budget=_budget(max_depth=2),
    )
    assert result.stats.solved
    assert Apply(primitive="twice", args=(PrimRef(name="rot90"), Input())) in result.ranked_programs


def test_beam_engine_also_solves() -> None:
    task = Task(task_id="t", train=(Example(input=_GRID, output=_transpose(_GRID)),), test=())
    engine = BeamBottomUpSearchEngine(
        constant_sources=(),
        function_hole_fill_mode="none",
        polymorphism_instantiation="monomorphize",
        unpinned_type_var_mode="reject",
        beam_width=50,
    )
    result = engine.run(
        train_examples=task.train,
        library=_GEO,
        constraints=(),
        cost=ProgramSize(),
        budget=_budget(max_depth=2),
    )
    assert Apply(primitive="transpose", args=(Input(),)) in result.ranked_programs
