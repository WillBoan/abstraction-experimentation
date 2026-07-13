"""``estimate_cost``: the static worst-case ``considered`` ceiling, cross-checked against the engine."""

from __future__ import annotations

from arc_lab.core.dataset import Corpus
from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.program_search.execution.estimate_cost import estimate_cost
from arc_lab.program_search.execution.model.config import Config
from arc_lab.program_search.execution.model.learn_spec import LearnSpec
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.cost import ProgramSize
from arc_lab.program_search.search.search_engine import (
    BeamBottomUpSearchEngine,
    BottomUpSearchEngine,
)
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.types import GRID

_GRID = Grid.from_list([[1, 2], [3, 4]])


def _transpose(grid: Grid) -> Grid:
    return Grid.from_list([list(col) for col in zip(*grid.to_list(), strict=True)])


_TRANSPOSE = Primitive(name="transpose", param_types=(GRID,), return_type=GRID, impl=_transpose)
_EMPTY = Library(name="empty", primitives=())
_GEO = Library(name="geo", primitives=(_TRANSPOSE,))

_ENGINE = BottomUpSearchEngine(
    constant_sources=(),
    function_hole_fill_mode="none",
    polymorphism_instantiation="monomorphize",
    unpinned_type_var_mode="reject",
)


def _task() -> Task:
    return Task(task_id="t", train=(Example(input=_GRID, output=_transpose(_GRID)),), test=())


def _run_spec(library: Library, budget: Budget, task: Task) -> RunSpec:
    config = Config(library=library, search_engine=_ENGINE, budget=budget)
    return RunSpec(config=config, corpus=Corpus.of("c", (task,)))


def test_leaf_only_round_matches_the_engine_exactly() -> None:
    task = _task()
    budget = Budget(max_depth=1, max_arity=1, max_pool=100)
    estimate = estimate_cost(_run_spec(_EMPTY, budget, task))
    result = _ENGINE.run(
        train_examples=task.train, library=_EMPTY, constraints=(), cost=ProgramSize(), budget=budget
    )
    assert estimate.total_considered_ceiling == result.stats.considered == 1  # just Input()


def test_single_unary_primitive_matches_the_engine_exactly() -> None:
    task = _task()
    budget = Budget(max_depth=2, max_arity=1, max_pool=100)
    estimate = estimate_cost(_run_spec(_GEO, budget, task))
    result = _ENGINE.run(
        train_examples=task.train, library=_GEO, constraints=(), cost=ProgramSize(), budget=budget
    )
    # Input() at round 0, transpose(Input()) at round 1 — no unify failures possible here, so the
    # ceiling (which assumes every combination succeeds) is exact.
    assert estimate.total_considered_ceiling == result.stats.considered == 2


def test_ceiling_is_never_below_actual_considered_with_a_mixed_type_library() -> None:
    """A library with types that fail to unify against each other: the engine prunes, the ceiling
    counts the full attempted cartesian product either way — so it must stay >= actual."""

    def _double(n: int) -> int:
        return n * 2

    from arc_lab.program_search.substrate.types import INT

    double = Primitive(name="double", param_types=(INT,), return_type=INT, impl=_double)
    library = Library(name="mixed", primitives=(_TRANSPOSE, double))
    task = _task()
    budget = Budget(max_depth=3, max_arity=1, max_pool=100)
    estimate = estimate_cost(_run_spec(library, budget, task))
    result = _ENGINE.run(
        train_examples=task.train,
        library=library,
        constraints=(),
        cost=ProgramSize(),
        budget=budget,
    )
    assert estimate.total_considered_ceiling >= result.stats.considered


def test_pool_is_capped_at_max_pool_across_rounds() -> None:
    task = _task()
    budget = Budget(max_depth=4, max_arity=1, max_pool=3)
    estimate = estimate_cost(_run_spec(_GEO, budget, task))
    for round_ in estimate.tasks[0].rounds:
        assert round_.incoming_pool <= 3


def test_beam_engine_caps_by_beam_width_not_max_pool() -> None:
    beam = BeamBottomUpSearchEngine(
        constant_sources=(),
        function_hole_fill_mode="none",
        polymorphism_instantiation="monomorphize",
        unpinned_type_var_mode="reject",
        beam_width=2,
    )
    task = _task()
    budget = Budget(max_depth=4, max_arity=1, max_pool=100)
    config = Config(library=_GEO, search_engine=beam, budget=budget)
    estimate = estimate_cost(RunSpec(config=config, corpus=Corpus.of("c", (task,))))
    for round_ in estimate.tasks[0].rounds:
        assert round_.incoming_pool <= 2


def test_flags_lambda_synthesis_as_a_lower_bound_only() -> None:
    engine = BottomUpSearchEngine(
        constant_sources=(),
        function_hole_fill_mode="lambda-synthesis",
        polymorphism_instantiation="monomorphize",
        unpinned_type_var_mode="reject",
    )
    budget = Budget(max_depth=2, max_arity=1, max_pool=100)
    config = Config(library=_EMPTY, search_engine=engine, budget=budget)
    estimate = estimate_cost(RunSpec(config=config, corpus=Corpus.of("c", (_task(),))))
    assert any("LOWER bound" in flag for flag in estimate.flags)


def test_flags_a_learn_run_as_bounding_iteration_zero_only() -> None:
    budget = Budget(max_depth=1, max_arity=1, max_pool=100)
    learn = LearnSpec(learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()), iterations=1)
    config = Config(library=_EMPTY, search_engine=_ENGINE, budget=budget, learn=learn)
    estimate = estimate_cost(RunSpec(config=config, corpus=Corpus.of("c", (_task(),))))
    assert any("LEARN run" in flag for flag in estimate.flags)


def test_no_flags_for_a_plain_search_preset_shaped_config() -> None:
    budget = Budget(max_depth=2, max_arity=1, max_pool=100)
    estimate = estimate_cost(_run_spec(_GEO, budget, _task()))
    assert estimate.flags == ()
