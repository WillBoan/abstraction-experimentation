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
from arc_lab.program_search.substrate.program import Apply, Input

_GRID = Grid.from_list([[1, 2], [3, 4]])
_TRANSPOSED = Grid.from_list([[1, 3], [2, 4]])
_EMPTY = Library(name="empty", primitives=())
_ENGINE = BottomUpSearchEngine(
    constant_sources=(),
    function_hole_fill_mode="none",
    polymorphism_instantiation="monomorphize",
    unpinned_type_var_mode="reject",
)


def _run(library: Library, output: Grid, depth_limit: int) -> SearchResult:
    task = Task(task_id="t", train=(Example(input=_GRID, output=output),), test=())
    return _ENGINE.run(
        train_examples=task.train,
        library=library,
        constraints=(),
        cost=ProgramSize(),
        budget=Budget(depth_limit=depth_limit, max_arity=1, max_pool=100),
    )


def test_solution_sink_records_the_identity_solution() -> None:
    stats = _run(_EMPTY, _GRID, depth_limit=0).stats
    assert stats.solved  # pool-based, unchanged this commit
    assert stats.solution_count == 1  # only Input() reproduces the identity output
    assert stats.first_solution_index is not None
    assert stats.cheapest_solution_index == stats.first_solution_index
    assert not stats.solutions_truncated
    assert tuple(record.program for record in stats.solutions) == (Input(),)


def test_generations_funnel_has_one_row_per_round() -> None:
    stats = _run(D4_LIBRARY, _TRANSPOSED, depth_limit=2).stats
    assert len(stats.generations) == 3  # rounds 0, 1, 2 (search always runs the full budget)
    assert all("composed" in row and "pool_size_start" in row for row in stats.generations)
    assert stats.solution_count >= 1  # transpose(input) is found at round 1


def test_eviction_loss_is_recovered_by_the_sink() -> None:
    # max_pool=1 forces the cost-2 solution flip_h(input) to be evicted by the cheaper cost-1
    # Input() leaf. Pool-based extraction would report the task unsolved; the sink recovers the
    # solution, and stats.accepted==0 (pool) alongside stats.solved (sink) is the eviction-loss gap.
    flipped = Grid.from_list([[2, 1], [4, 3]])
    task = Task(task_id="ev", train=(Example(input=_GRID, output=flipped),), test=())
    result = _ENGINE.run(
        train_examples=task.train,
        library=D4_LIBRARY,
        constraints=(),
        cost=ProgramSize(),
        budget=Budget(depth_limit=1, max_arity=1, max_pool=1),
    )
    assert result.stats.solved  # sink-based: the evicted solution is recovered
    assert result.stats.accepted == 0  # pool partition: it was evicted, so no frontier survivor
    assert result.ranked_programs == (Apply("flip_h", (Input(),)),)


def test_multiple_distinct_solutions_are_all_returned_cheapest_first() -> None:
    # A fully-symmetric grid is fixed by Input() AND every D4 op, so the sink records many distinct
    # solution PROGRAMS (the pool dedups them to one slot). All are returned cheapest-first, so
    # predict has real attempts_per_test candidates (the wakeup).
    symmetric = Grid.from_list([[5, 5], [5, 5]])
    task = Task(task_id="sym", train=(Example(input=symmetric, output=symmetric),), test=())
    result = _ENGINE.run(
        train_examples=task.train,
        library=D4_LIBRARY,
        constraints=(),
        cost=ProgramSize(),
        budget=Budget(depth_limit=1, max_arity=1, max_pool=100),
    )
    assert len(result.ranked_programs) >= 2  # Input() plus the cost-2 D4 applications
    assert result.ranked_programs[0] == Input()  # cheapest first
    assert result.stats.returned_solution_count == len(result.ranked_programs)


def test_unsolved_task_has_empty_sink_and_is_not_solved() -> None:
    # An unreachable target at this budget: no solution, so the sink is empty and .solved is False.
    unreachable = Grid.from_list([[9, 9], [9, 9]])
    stats = _run(_EMPTY, unreachable, depth_limit=0).stats
    assert not stats.solved
    assert stats.solution_count == 0
    assert stats.first_solution_index is None
    assert stats.cheapest_solution_index is None
