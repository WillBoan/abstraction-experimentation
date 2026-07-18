"""Commit-2 telemetry: the solution sink + per-generation funnel are recorded (and dormant —
the returned result and ``.solved`` are still pool-based this commit)."""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.cost import ProgramSize
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.search.search_result import SearchResult
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.program import Input

_GRID = Grid.from_list([[1, 2], [3, 4]])
_TRANSPOSED = Grid.from_list([[1, 3], [2, 4]])
_EMPTY = Library(name="empty", primitives=())
_ENGINE = BottomUpSearchEngine(
    constant_sources=(),
    function_hole_fill_mode="none",
    polymorphism_instantiation="monomorphize",
    unpinned_type_var_mode="reject",
)


def _run(library: Library, output: Grid, max_depth: int) -> SearchResult:
    task = Task(task_id="t", train=(Example(input=_GRID, output=output),), test=())
    return _ENGINE.run(
        train_examples=task.train,
        library=library,
        constraints=(),
        cost=ProgramSize(),
        budget=Budget(max_depth=max_depth, max_arity=1, max_pool=100),
    )


def test_solution_sink_records_the_identity_solution() -> None:
    stats = _run(_EMPTY, _GRID, max_depth=1).stats
    assert stats.solved  # pool-based, unchanged this commit
    assert stats.solution_count == 1  # only Input() reproduces the identity output
    assert stats.first_solution_index is not None
    assert stats.cheapest_solution_index == stats.first_solution_index
    assert not stats.solutions_truncated
    assert tuple(record.program for record in stats.solutions) == (Input(),)


def test_generations_funnel_has_one_row_per_round() -> None:
    stats = _run(D4_LIBRARY, _TRANSPOSED, max_depth=3).stats
    assert len(stats.generations) == 3  # rounds 0, 1, 2 (search always runs the full budget)
    assert all("composed" in row and "pool_size_start" in row for row in stats.generations)
    assert stats.solution_count >= 1  # transpose(input) is found at round 1


def test_sink_dormant_leaves_return_pool_based_when_unsolved() -> None:
    # An unreachable target at this budget: no solution, so the sink is empty and .solved is False.
    unreachable = Grid.from_list([[9, 9], [9, 9]])
    stats = _run(_EMPTY, unreachable, max_depth=1).stats
    assert not stats.solved
    assert stats.solution_count == 0
    assert stats.first_solution_index is None
    assert stats.cheapest_solution_index is None
