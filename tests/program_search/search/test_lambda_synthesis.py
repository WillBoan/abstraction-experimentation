"""Lambda synthesis (§5.3), ``body_sampler`` (§7/§11.4), and memoization (§9) of ARCHITECTURE.md.

The slice-4 capability: a higher-order primitive's function hole filled by a *recursively
synthesized* ``Lam`` — culminating in ``build_grid`` solving a size-general task end-to-end. Slice 5
generalized propagation into the recursively-threaded ``EnclosingTarget`` (§7) and made
``enclosing_target`` part of the memoization key (§9) — both covered here.
"""

from __future__ import annotations

import logging

import pytest

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task, TrainExamples, train_with_output
from arc_lab.program_search.search import search_engine as search_engine_module
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.context import Context
from arc_lab.program_search.search.cost import ProgramSize
from arc_lab.program_search.search.leaves import ConstantSource
from arc_lab.program_search.search.scope import Scope
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine, _RunState
from arc_lab.program_search.search.search_result import SearchResult
from arc_lab.program_search.search.tracking import SearchTracker
from arc_lab.program_search.substrate.library import (
    BodySampler,
    Closure,
    EnclosingTarget,
    Library,
    Primitive,
    RawContext,
    Value,
)
from arc_lab.program_search.substrate.primitives.build import BUILD_GRID, BUILD_LIBRARY
from arc_lab.program_search.substrate.program import Apply, Const, Input, Lam, Var
from arc_lab.program_search.substrate.types import COLOR, GRID, INT, ArrowType


def _transpose(grid: Grid) -> Grid:
    return Grid.from_list([list(col) for col in zip(*grid.to_list(), strict=True)])


def _engine(constant_sources: tuple[ConstantSource, ...] = ()) -> BottomUpSearchEngine:
    return BottomUpSearchEngine(
        constant_sources=constant_sources,
        function_hole_fill_mode="lambda-synthesis",
        polymorphism_instantiation="monomorphize",
        unpinned_type_var_mode="reject",
    )


def _budget(depth_limit: int) -> Budget:
    return Budget(depth_limit=depth_limit, max_arity=1, max_pool=500)


# -- the body_sampler substrate field (§11.4) ------------------------------------------------


def test_build_grid_sampler_aligns_contexts_with_output_cells() -> None:
    grid = Grid.from_list([[1, 2, 3], [4, 5, 6]])
    output = _transpose(grid)  # 3x2
    task = Task(task_id="t", train=(Example(input=grid, output=output),), test=())
    assert BUILD_GRID.body_sampler is not None
    enclosing_target = EnclosingTarget((output,), GRID)
    contexts, target = BUILD_GRID.body_sampler(task.train, (), enclosing_target)
    assert target is not None and len(contexts) == len(target) == 6
    # Row-major over the *output* grid, scope binding = (row, col) — §3 ordering.
    assert contexts[0] == (grid, (0, 0))
    assert contexts[1] == (grid, (0, 1))
    assert target == tuple(color for row in output.to_list() for color in row)


def test_build_grid_sampler_without_an_enclosing_target_yields_nothing() -> None:
    grid = Grid.from_list([[1, 2], [3, 4]])
    task = Task(task_id="t", train=(Example(input=grid, output=grid),), test=())
    assert BUILD_GRID.body_sampler is not None
    contexts, target = BUILD_GRID.body_sampler(task.train, (), None)
    assert contexts == () and target is None


def test_body_sampler_is_code_and_never_serialized() -> None:
    assert "body_sampler" not in BUILD_GRID.to_dict()


# -- synthesis mechanics: propagation vs. baseline (§5.3, §8) --------------------------------
#
# `paint(grid, fn)` fills the whole grid with `fn(0)` — a minimal higher-order primitive whose
# hole must be a synthesized lambda (no pooled function value has type INT → COLOR). `paint`'s
# return type is GRID, so the engine hands its sampler a non-`None` `enclosing_target` (the
# training outputs) — `_propagated_sampler` consults it; `_baseline_sampler` ignores it.


def _paint(grid: Grid, fn: Value) -> Grid:
    if not isinstance(fn, Closure):
        raise TypeError("paint expects a function value")
    color = fn(0)
    if not isinstance(color, int):
        raise TypeError("paint body must yield a color")
    return Grid.from_list([[color] * grid.width for _ in range(grid.height)])


def _paint_contexts(train_examples: TrainExamples) -> tuple[RawContext, ...]:
    return tuple((example.input, (0,)) for example in train_with_output(train_examples))


def _propagated_sampler(
    train_examples: TrainExamples,
    sibling_arg_values: tuple[tuple[Value, ...] | None, ...],
    enclosing_target: EnclosingTarget | None,
) -> tuple[tuple[RawContext, ...], tuple[Value, ...] | None]:
    contexts = _paint_contexts(train_examples)
    if enclosing_target is None:
        return contexts, None
    target: list[Value] = []
    for output in enclosing_target.values:
        if not isinstance(output, Grid):
            return contexts, None
        target.append(output.to_list()[0][0])
    return contexts, tuple(target)


def _baseline_sampler(
    train_examples: TrainExamples,
    sibling_arg_values: tuple[tuple[Value, ...] | None, ...],
    enclosing_target: EnclosingTarget | None,
) -> tuple[tuple[RawContext, ...], tuple[Value, ...] | None]:
    # no derivable target: the complete baseline carries the search (§8), even with a live target.
    return _paint_contexts(train_examples), None


def _paint_primitive(sampler: BodySampler) -> Library:
    paint = Primitive(
        name="paint",
        param_types=(GRID, ArrowType((INT,), COLOR)),
        return_type=GRID,
        impl=_paint,
        body_sampler=sampler,
    )
    return Library(name="paint", primitives=(paint,))


_PAINT_SOLUTION = Apply(
    primitive="paint",
    args=(Input(), Lam(param_type=INT, body=Const(value=5, value_type=COLOR))),
)


def _run_paint(sampler: BodySampler) -> SearchResult:
    task = Task(
        task_id="p",
        train=(Example(input=Grid.from_list([[3]]), output=Grid.from_list([[5]])),),
        test=(),
    )
    engine = _engine(constant_sources=("finite-enumerate",))
    return engine.run(
        train_examples=task.train,
        library=_paint_primitive(sampler),
        constraints=(),
        cost=ProgramSize(),
        budget=_budget(depth_limit=2),
    )


def test_synthesized_lambda_fills_the_hole_with_propagation() -> None:
    result = _run_paint(_propagated_sampler)
    assert result.stats.solved
    assert _PAINT_SOLUTION in result.ranked_programs


def test_baseline_without_a_body_target_still_solves() -> None:
    result = _run_paint(_baseline_sampler)
    assert result.stats.solved
    assert _PAINT_SOLUTION in result.ranked_programs


def test_propagation_considers_fewer_candidates_than_the_baseline() -> None:
    propagated = _run_paint(_propagated_sampler).stats.considered
    baseline = _run_paint(_baseline_sampler).stats.considered
    assert propagated < baseline


# -- progress logging: the lambda-synthesis summary line (run.log) --------------------------


def test_lambda_synthesis_logs_a_summary_when_non_trivial(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Both thresholds are wall-clock/candidate-count gated to avoid flooding run.log with the
    # near-instant sub-searches that make up most lambda-synthesis calls — lowered here so this
    # tiny fixture still exercises the log line, rather than needing a slow, large one.
    monkeypatch.setattr(search_engine_module, "_LAMBDA_SYNTHESIS_LOG_MIN_SECONDS", 0.0)
    monkeypatch.setattr(search_engine_module, "_LAMBDA_SYNTHESIS_LOG_MIN_CONSIDERED", 0)
    task = Task(
        task_id="paint-task",
        train=(Example(input=Grid.from_list([[3]]), output=Grid.from_list([[5]])),),
        test=(),
    )
    tracker = SearchTracker(task_id=task.task_id)
    engine = _engine(constant_sources=("finite-enumerate",))
    with caplog.at_level(logging.INFO, logger="arc_lab.program_search.search.search_engine"):
        engine.run(
            train_examples=task.train,
            library=_paint_primitive(_propagated_sampler),
            constraints=(),
            cost=ProgramSize(),
            budget=_budget(depth_limit=2),
            tracker=tracker,
        )
    lambda_records = [r for r in caplog.records if r.getMessage().startswith("Lambda synthesis")]
    assert lambda_records, "expected at least one lambda-synthesis summary line"
    for record in lambda_records:
        assert "primitive paint" in record.getMessage()
        assert record.task_id == "paint-task"  # type: ignore[attr-defined]
        assert record.generation.endswith("/3")  # type: ignore[attr-defined]


def test_lambda_synthesis_is_silent_when_trivial(caplog: pytest.LogCaptureFixture) -> None:
    """Default thresholds keep this tiny fixture's (near-instant) sub-searches out of run.log."""
    with caplog.at_level(logging.INFO, logger="arc_lab.program_search.search.search_engine"):
        _run_paint(_propagated_sampler)
    assert not any(r.getMessage().startswith("Lambda synthesis") for r in caplog.records)


# -- the payoff: build_grid solves a size-general task end-to-end ----------------------------


def test_build_grid_solves_size_general_transpose() -> None:
    a = Grid.from_list([[1, 2, 3], [4, 5, 6]])  # 2x3
    b = Grid.from_list([[7, 8], [9, 0], [1, 2]])  # 3x2 — a *different* size: forces generality
    task = Task(
        task_id="transpose",
        train=(
            Example(input=a, output=_transpose(a)),
            Example(input=b, output=_transpose(b)),
        ),
        test=(),
    )
    result = _engine().run(
        train_examples=task.train,
        library=BUILD_LIBRARY,
        constraints=(),
        cost=ProgramSize(),
        budget=_budget(depth_limit=2),
    )
    assert result.stats.solved
    # build_grid(width(input), height(input), lam(lam(read(input, $0, $1)))) — §3: $1=row, $0=col.
    body = Apply(
        primitive="read",
        args=(Input(), Var(index=0, value_type=INT), Var(index=1, value_type=INT)),
    )
    expected = Apply(
        primitive="build_grid",
        args=(
            Apply(primitive="width", args=(Input(),)),
            Apply(primitive="height", args=(Input(),)),
            Lam(param_type=INT, body=Lam(param_type=INT, body=body)),
        ),
    )
    assert expected in result.ranked_programs
    # Size-generality — the capability this slice exists for: correct on an unseen size.
    held_out = Grid.from_list([[1, 0, 2, 3]])  # 1x4, unlike either training pair
    solution = result.ranked_programs[0]
    assert solution.evaluate_grid(held_out, BUILD_LIBRARY) == _transpose(held_out)


# -- memoization (§9), including enclosing_target as part of the key -------------------------


def test_enumerate_is_memoized_within_a_run() -> None:
    grid = Grid.from_list([[1, 2], [3, 4]])
    task = Task(task_id="m", train=(Example(input=grid, output=grid),), test=())
    engine = _engine()
    budget = _budget(depth_limit=1)
    state = _RunState(train_examples=task.train, library=BUILD_LIBRARY, cost=ProgramSize())
    contexts = (Context(grid),)

    first = engine._enumerate(Scope(()), contexts, budget, state, None)
    considered = state.tracker.considered
    again = engine._enumerate(Scope(()), contexts, budget, state, None)
    assert again is first  # served from the memo…
    assert state.tracker.considered == considered  # …with no re-enumeration work

    shallower = engine._enumerate(Scope(()), contexts, budget.descend(), state, None)
    assert shallower is not first  # a different budget is a different key — no false sharing


def test_enclosing_target_is_part_of_the_memo_key() -> None:
    """Two different ``enclosing_target``s at an identical ``(scope, contexts, budget)`` must not
    collide in the memo — a real soundness requirement (§9), not just an API nicety: which
    candidates a nested lambda synthesis absorbs into its own pool can depend on the target in
    force, so serving one recursion path's cached pool to another with a different target would be
    silently wrong."""
    grid = Grid.from_list([[1, 2], [3, 4]])
    task = Task(task_id="m", train=(Example(input=grid, output=grid),), test=())
    engine = _engine()
    budget = _budget(depth_limit=1)
    state = _RunState(train_examples=task.train, library=BUILD_LIBRARY, cost=ProgramSize())
    contexts = (Context(grid),)

    target_a = EnclosingTarget((grid,), GRID)
    target_b = EnclosingTarget((Grid.from_list([[9]]),), GRID)
    pool_a = engine._enumerate(Scope(()), contexts, budget, state, target_a)
    pool_b = engine._enumerate(Scope(()), contexts, budget, state, target_b)
    assert pool_a is not pool_b
    # Re-requesting the first target is still a cache hit.
    assert engine._enumerate(Scope(()), contexts, budget, state, target_a) is pool_a
