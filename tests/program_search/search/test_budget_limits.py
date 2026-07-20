"""The two ``Budget`` stop limits: ``considered_limit`` and ``solution_limit``.

Both end a search outright (unlike ``max_arity``/``max_pool``, which only shape the space), and
each takes a ``*_mode``: stop the instant it trips, or finish the current generation first. The
four combinations mean genuinely different things, so most of this file is one fixture run through
all of them -- the cheapest way to stop any pairing from silently collapsing into another.

The invariant every case re-asserts is the outcome partition, ``considered == sum(outcomes)``: it
is what breaks first if an abort leaves candidates counted but unresolved.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.cost import ProgramSize
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.search.search_result import SearchResult
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.primitives.build import BUILD_LIBRARY
from arc_lab.program_search.substrate.types import GRID

_A = Grid.from_list([[1, 2], [3, 4]])
_B = Grid.from_list([[5, 6], [7, 8]])


def _transpose(grid: Grid) -> Grid:
    return Grid.from_list([list(col) for col in zip(*grid.to_list(), strict=True)])


def _flip(grid: Grid) -> Grid:
    return Grid.from_list([list(reversed(row)) for row in grid.to_list()])


_TRANSPOSE = Primitive(name="transpose", param_types=(GRID,), return_type=GRID, impl=_transpose)
_FLIP = Primitive(name="flip", param_types=(GRID,), return_type=GRID, impl=_flip)
#: Two unary GRID->GRID primitives compose into a pool that grows every round, so a limit set
#: mid-run has somewhere to bite.
_GEO = Library(name="geo", primitives=(_TRANSPOSE, _FLIP))

_ENGINE = BottomUpSearchEngine(
    constant_sources=(),
    function_hole_fill_mode="none",
    polymorphism_instantiation="monomorphize",
    unpinned_type_var_mode="reject",
)


def _task(fn: object = _transpose) -> Task:
    assert callable(fn)
    return Task(
        task_id="t",
        train=(Example(input=_A, output=fn(_A)), Example(input=_B, output=fn(_B))),
        test=(),
    )


def _budget(**overrides: Any) -> Budget:
    return replace(Budget(depth_limit=4, max_arity=1, max_pool=200), **overrides)


def _run(budget: Budget, task: Task | None = None, library: Library = _GEO) -> SearchResult:
    return _ENGINE.run(
        train_examples=(task or _task()).train,
        library=library,
        constraints=(),
        cost=ProgramSize(),
        budget=budget,
    )


def _partition_holds(result: SearchResult) -> bool:
    return result.stats.considered == sum(result.stats.outcomes.values())


def _incomplete_rows(result: SearchResult) -> list[int]:
    return [i for i, gen in enumerate(result.stats.generations) if gen.get("incomplete")]


# -- no limits: the defaults must be a pure no-op --------------------------------------------


def test_defaults_leave_the_search_untouched() -> None:
    """Nothing in a preset sets these fields, so this is the guarantee the regression locks rest on."""
    result = _run(_budget())
    assert not result.stats.censored
    assert not result.stats.stopped_early
    assert result.stats.censored_at_generation is None
    assert _incomplete_rows(result) == []
    assert _partition_holds(result)


# -- considered_limit ------------------------------------------------------------------------


def test_considered_limit_immediate_is_exact() -> None:
    """``==``, not ``<=``. Exactness is the whole point: a censored baseline's ``considered`` is a
    denominator, and a cost-matched control that overshoots is not matched."""
    uncapped = _run(_budget())
    cap = uncapped.stats.considered // 3
    assert cap >= 1
    result = _run(_budget(considered_limit=cap))
    assert result.stats.considered == cap
    assert result.stats.censored
    assert not result.stats.stopped_early
    assert _partition_holds(result)


def test_considered_limit_immediate_flags_the_round_it_cut_short() -> None:
    uncapped = _run(_budget())
    result = _run(_budget(considered_limit=uncapped.stats.considered // 3))
    assert _incomplete_rows(result) == [len(result.stats.generations) - 1]
    assert result.stats.censored_at_generation == len(result.stats.generations) - 1


def test_considered_limit_generation_end_overshoots_but_leaves_no_partial_round() -> None:
    """The mode that exists for ``_estimate_raw_cost``: it wants a clean per-round growth series,
    which an ``immediate`` abort cannot give it."""
    uncapped = _run(_budget())
    cap = uncapped.stats.considered // 3
    result = _run(_budget(considered_limit=cap, considered_limit_mode="generation-end"))
    assert result.stats.considered >= cap
    assert _incomplete_rows(result) == []
    assert _partition_holds(result)


def test_considered_limit_generation_end_stops_before_the_budgeted_depth() -> None:
    uncapped = _run(_budget())
    # Small enough to trip during an early round, so there are rounds left to skip.
    cap = int(uncapped.stats.generations[0]["composed"] or 0) + 1
    result = _run(_budget(considered_limit=cap, considered_limit_mode="generation-end"))
    assert result.stats.censored
    assert len(result.stats.generations) < len(uncapped.stats.generations)
    assert _partition_holds(result)


def test_considered_limit_does_not_drain_the_already_built_candidates() -> None:
    """``immediate`` discards candidates already composed but not yet absorbed rather than
    absorbing them. Draining would overshoot the cap -- so this is the same claim as exactness,
    asserted across a range of caps where the buffered function/branch candidates differ."""
    uncapped = _run(_budget())
    for divisor in (2, 3, 5, 7):
        cap = max(1, uncapped.stats.considered // divisor)
        result = _run(_budget(considered_limit=cap))
        assert result.stats.considered == cap
        assert _partition_holds(result)


# -- solution_limit --------------------------------------------------------------------------


def test_solution_limit_generation_end_still_solves_and_keeps_the_round_intact() -> None:
    uncapped = _run(_budget())
    assert uncapped.stats.solved
    result = _run(_budget(solution_limit=1))  # generation-end is the default
    assert result.stats.solved
    assert result.stats.stopped_early
    assert not result.stats.censored
    assert _incomplete_rows(result) == []
    assert result.stats.considered < uncapped.stats.considered
    assert _partition_holds(result)


def test_solution_limit_generation_end_retains_the_same_program_as_an_uncapped_run() -> None:
    """Finishing the generation is what buys this: it retains the cheapest solution of the solve
    generation rather than merely the first one absorbed."""
    uncapped = _run(_budget())
    result = _run(_budget(solution_limit=1))
    assert result.ranked_programs[:1] == uncapped.ranked_programs[:1]


def test_solution_limit_immediate_stops_sooner_and_leaves_a_partial_round() -> None:
    """The two modes must stay distinguishable: same fixture, strictly less work, and the partial
    final round that ``generation-end`` deliberately avoids."""
    generation_end = _run(_budget(solution_limit=1))
    immediate = _run(_budget(solution_limit=1, solution_limit_mode="immediate"))
    assert immediate.stats.solved
    assert immediate.stats.stopped_early
    assert immediate.stats.considered < generation_end.stats.considered
    assert _incomplete_rows(immediate) == [len(immediate.stats.generations) - 1]
    assert _partition_holds(immediate)


def test_solution_limit_immediate_still_pools_the_solution_that_tripped_it() -> None:
    """The regression for raising in the wrong place. The abort fires AFTER ``pool.add_dedup``;
    raising between ``record_solution`` and ``add_dedup`` would leave the solution out of the pool
    and ``extract`` would report the run unsolved -- the exact opposite of what early stop is for."""
    result = _run(_budget(solution_limit=1, solution_limit_mode="immediate"))
    assert result.stats.solved
    assert result.ranked_programs
    assert result.stats.solution_count >= 1


def test_censored_and_stopped_early_are_different_verdicts() -> None:
    """One says the search was cut short (unsolved is a lower bound); the other says it succeeded
    and stopped paying. The ladder certificate keys off exactly this distinction."""
    stopped = _run(_budget(solution_limit=1))
    censored = _run(_budget(considered_limit=1))  # too tight to reach the solution
    assert (censored.stats.censored, censored.stats.stopped_early) == (True, False)
    assert (stopped.stats.censored, stopped.stats.stopped_early) == (False, True)
    assert not censored.stats.solved
    assert stopped.stats.solved


def test_censored_does_not_imply_unsolved() -> None:
    """A limit that trips AFTER the solution was absorbed still censors the run: the search was cut
    short, so the solution stands but "no cheaper one exists" was never established.

    Recorded because the ladder certificate depends on the ordering: it tests `solved` FIRST, so a
    censored-but-solved probe still reports a skip path (a real defect) rather than being softened
    to inconclusive. Censoring can only ever weaken a *negative*, never overturn a positive.
    """
    uncapped = _run(_budget())
    assert uncapped.stats.first_solution_index is not None
    cap = uncapped.stats.first_solution_index + 2
    assert cap < uncapped.stats.considered  # the limit really does cut the run short
    result = _run(_budget(considered_limit=cap))
    assert result.stats.censored
    assert result.stats.solved


# -- the abort path through a lambda-synthesis sub-search ------------------------------------


def _lambda_engine() -> BottomUpSearchEngine:
    return BottomUpSearchEngine(
        constant_sources=("harvest-from-instance",),
        function_hole_fill_mode="lambda-synthesis",
        polymorphism_instantiation="monomorphize",
        unpinned_type_var_mode="reject",
    )


def _lambda_run(budget: Budget) -> SearchResult:
    # Two differently-SIZED examples: forces a size-general solution, which is what actually drives
    # the engine into recursive lambda-body searches (the frames this abort has to unwind through).
    tall = Grid.from_list([[7, 8], [9, 0], [1, 2]])
    task = Task(
        task_id="transpose",
        train=(
            Example(input=_A, output=_transpose(_A)),
            Example(input=tall, output=_transpose(tall)),
        ),
        test=(),
    )
    return _lambda_engine().run(
        train_examples=task.train,
        library=BUILD_LIBRARY,
        constraints=(),
        cost=ProgramSize(),
        budget=budget,
    )


@pytest.mark.parametrize("divisor", [2, 3, 5, 9])
def test_partition_survives_an_abort_inside_a_sub_search(divisor: int) -> None:
    """The case ``_finalize_sub_pool`` exists for.

    A lambda-synthesis sub-search absorbs into its own pool while sharing the run's one tracker, so
    an abort partway through leaves every intervening frame holding counted-but-unresolved entries.
    Each frame must resolve its own pool as ``GOAL_UNMATCHED`` on the way up; a plain re-raise
    passes the happy-path tests and breaks the partition only here.

    Several caps, because which frame the abort lands in depends on where the count falls.
    """
    uncapped = _lambda_run(Budget(depth_limit=2, max_arity=1, max_pool=500))
    cap = max(1, uncapped.stats.considered // divisor)
    result = _lambda_run(Budget(depth_limit=2, max_arity=1, max_pool=500, considered_limit=cap))
    assert result.stats.considered == cap
    assert _partition_holds(result)


def test_the_abort_is_not_swallowed_by_a_sub_searchs_exception_handling() -> None:
    """``_SearchAborted`` derives from ``BaseException`` for one reason: ``_evaluate_siblings`` and
    ``_sample_type`` catch bare ``Exception`` and sit directly on the unwind path out of a
    lambda-synthesis sub-search. As an ``Exception`` subclass the abort would be swallowed there and
    the search would sail past its limit -- which is what this asserts cannot happen.
    """
    uncapped = _lambda_run(Budget(depth_limit=2, max_arity=1, max_pool=500))
    cap = max(1, uncapped.stats.considered // 4)
    result = _lambda_run(Budget(depth_limit=2, max_arity=1, max_pool=500, considered_limit=cap))
    assert result.stats.considered == cap  # not "somewhat more than cap"
    assert result.stats.considered < uncapped.stats.considered


# -- the truncated pool must never be memoized -----------------------------------------------


def test_an_aborted_pool_is_not_cached() -> None:
    """``_enumerate`` writes its memo entry AFTER the round loop, so an abort skips it. That
    placement is load-bearing and invisible: hoisting the write into the loop would serve a
    truncated pool to a later call with the same key as though enumeration had completed.

    Asserted behaviourally -- a capped run followed by an uncapped one at the same key must not
    inherit the capped run's short pool.
    """
    uncapped = _run(_budget())
    cap = max(1, uncapped.stats.considered // 3)
    engine, task = _ENGINE, _task()

    capped_first = engine.run(
        train_examples=task.train,
        library=_GEO,
        constraints=(),
        cost=ProgramSize(),
        budget=_budget(considered_limit=cap),
    )
    assert capped_first.stats.considered == cap
    # A fresh run at the same key: full cost and the same answer as the never-capped run.
    after = _run(_budget())
    assert after.stats.considered == uncapped.stats.considered
    assert after.ranked_programs == uncapped.ranked_programs
