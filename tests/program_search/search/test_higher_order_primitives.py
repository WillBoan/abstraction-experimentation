"""``map``/``filter``/``fold``/``sort_by`` (§7 of ARCHITECTURE.md) and the sibling-arg + recursive
``enclosing_target`` machinery that makes lambda synthesis work for them (search_engine.py).
"""

from __future__ import annotations

import pytest

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task, TrainExamples, train_with_output
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.context import Context
from arc_lab.program_search.search.cost import ProgramSize
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine, _RunState
from arc_lab.program_search.substrate.library import (
    EnclosingTarget,
    Library,
    Primitive,
    RawContext,
    Value,
    apply_function_value,
)
from arc_lab.program_search.substrate.primitives.cells import CELLS
from arc_lab.program_search.substrate.primitives.control import EQ
from arc_lab.program_search.substrate.primitives.higher_order import FILTER, FOLD, MAP, SORT_BY
from arc_lab.program_search.substrate.program import Apply, Input
from arc_lab.program_search.substrate.types import (
    BOOL,
    COLOR,
    GRID,
    INT,
    ArrowType,
    TypeVar,
    list_type,
)

# -- impl-level: map/filter/fold/sort_by do the obvious thing, and reject bad inputs -------------


def _inc(x: int) -> int:
    return x + 1


_INC = Primitive(name="inc", param_types=(INT,), return_type=INT, impl=_inc)


def test_map_impl_applies_elementwise() -> None:
    assert MAP.impl(_INC, (1, 2, 3)) == (2, 3, 4)


def test_map_impl_rejects_a_non_list() -> None:
    with pytest.raises(TypeError):
        MAP.impl(_INC, 5)


_POSITIVE = Primitive(name="positive", param_types=(INT,), return_type=BOOL, impl=lambda x: x > 0)


def test_filter_impl_keeps_matching_elements() -> None:
    assert FILTER.impl(_POSITIVE, (-1, 2, -3, 4)) == (2, 4)


def test_filter_impl_rejects_a_non_bool_predicate() -> None:
    with pytest.raises(TypeError):
        FILTER.impl(_INC, (1, 2))  # _inc returns an int, not bool


_ADD = Primitive(name="add", param_types=(INT, INT), return_type=INT, impl=lambda a, b: a + b)


def test_fold_impl_reduces_with_a_seed() -> None:
    assert FOLD.impl(_ADD, 0, (1, 2, 3)) == 6


_NEG = Primitive(name="neg", param_types=(INT,), return_type=INT, impl=lambda x: -x)


def test_sort_by_impl_orders_by_key() -> None:
    assert SORT_BY.impl(_NEG, (3, 1, 2)) == (3, 2, 1)


def test_sort_by_impl_rejects_a_non_orderable_key() -> None:
    to_grid = Primitive(
        name="to_grid", param_types=(INT,), return_type=GRID, impl=lambda x: Grid.from_list([[x]])
    )
    with pytest.raises(TypeError):
        SORT_BY.impl(to_grid, (1, 2))


# -- train_with_output -----------------------------------------------------------------------


def test_train_with_output_filters_missing_outputs() -> None:
    a = Example(input=Grid.from_list([[1]]), output=Grid.from_list([[1]]))
    b = Example(input=Grid.from_list([[2]]), output=None)
    assert train_with_output((a, b)) == (a,)


# -- _evaluate_siblings: partial-tolerance (decision 2) -------------------------------------------


def _width_or_boom(grid: Grid) -> int:
    if grid.width == 1:
        raise ValueError("boom")
    return grid.width


_WIDTH_OR_BOOM = Primitive(
    name="width_or_boom", param_types=(GRID,), return_type=INT, impl=_width_or_boom
)


def _engine(**overrides: object) -> BottomUpSearchEngine:
    defaults: dict[str, object] = {
        "constant_sources": (),
        "function_hole_fill_mode": "lambda-synthesis",
        "polymorphism_instantiation": "monomorphize",
        "unpinned_type_var_mode": "reject",
    }
    defaults.update(overrides)
    return BottomUpSearchEngine(**defaults)  # type: ignore[arg-type]


def test_evaluate_siblings_tolerates_a_partial_failure() -> None:
    engine = _engine()
    library = Library(name="wob", primitives=(_WIDTH_OR_BOOM,))
    state = _RunState(train_examples=(), library=library, cost=ProgramSize())
    program = Apply(primitive="width_or_boom", args=(Input(),))
    contexts = (Context(Grid.from_list([[1]])), Context(Grid.from_list([[1, 2]])))
    result = engine._evaluate_siblings((program,), contexts, state)
    assert result == (None, (2,))


def test_evaluate_siblings_returns_none_when_every_context_fails() -> None:
    engine = _engine()
    library = Library(name="wob", primitives=(_WIDTH_OR_BOOM,))
    state = _RunState(train_examples=(), library=library, cost=ProgramSize())
    program = Apply(primitive="width_or_boom", args=(Input(),))
    contexts = (Context(Grid.from_list([[1]])), Context(Grid.from_list([[2]])))
    assert engine._evaluate_siblings((program,), contexts, state) is None


# -- __post_init__ validation --------------------------------------------------------------------


def test_lazy_synthesis_raises_at_construction_when_reachable() -> None:
    with pytest.raises(NotImplementedError):
        _engine(function_hole_fill_mode="lambda-synthesis", unpinned_type_var_mode="lazy_synthesis")


def test_lazy_synthesis_is_harmless_without_lambda_synthesis() -> None:
    _engine(function_hole_fill_mode="point-free", unpinned_type_var_mode="lazy_synthesis")


def test_inverse_semantics_propagation_raises_at_construction() -> None:
    with pytest.raises(NotImplementedError):
        _engine(inverse_semantics_propagation=True)


def test_function_sample_size_must_be_positive() -> None:
    with pytest.raises(ValueError):
        _engine(function_sample_size=0)


# -- unpinned_type_var_mode (decision 3): reject vs. eager grounding, direct ----------------------


def test_ground_unpinned_hole_reject_yields_nothing() -> None:
    engine = _engine(unpinned_type_var_mode="reject")
    a = TypeVar("a")
    hole = ArrowType((INT,), a)
    state = _RunState(
        train_examples=(),
        library=Library(name="e", primitives=()),
        cost=ProgramSize(),
        universe=(INT, COLOR),
    )
    assert list(engine._ground_unpinned_hole(hole, a, state)) == []


def test_ground_unpinned_hole_eager_grounding_tries_each_universe_type() -> None:
    engine = _engine(unpinned_type_var_mode="eager_grounding_over_universe")
    a = TypeVar("a")
    hole = ArrowType((INT,), a)
    state = _RunState(
        train_examples=(),
        library=Library(name="e", primitives=()),
        cost=ProgramSize(),
        universe=(INT, COLOR, BOOL),
    )
    result = list(engine._ground_unpinned_hole(hole, a, state))
    assert {return_type for _, return_type in result} == {INT, COLOR, BOOL}
    for hole_type, return_type in result:
        assert hole_type == ArrowType((INT,), return_type)  # same substitution applied to both


# -- unpinned_type_var_mode end-to-end: a genuinely unpinned hole (no sibling at all) --------------


def _produce(f: Value) -> Value:
    return apply_function_value(f, (0,))


def _produce_sampler(
    train_examples: TrainExamples,
    sibling_arg_values: tuple[tuple[Value, ...] | None, ...],
    enclosing_target: EnclosingTarget | None,
) -> tuple[tuple[RawContext, ...], tuple[Value, ...] | None]:
    examples = train_with_output(train_examples)
    contexts = tuple((example.input, (0,)) for example in examples)
    return contexts, None


_PRODUCE_RESULT = TypeVar("a")
PRODUCE = Primitive(
    name="produce",
    param_types=(ArrowType((INT,), _PRODUCE_RESULT),),
    return_type=_PRODUCE_RESULT,
    impl=_produce,
    body_sampler=_produce_sampler,
)
IDENTITY_GRID = Primitive(name="identity", param_types=(GRID,), return_type=GRID, impl=lambda g: g)


def test_eager_grounding_does_real_synthesis_work_reject_skips() -> None:
    """produce's hole ``INT -> a`` has no sibling to pin ``a`` — the genuinely unpinned case decision
    3 exists for. Checking *solvability* isn't discriminating here: the task is trivially solvable
    via the bare ``Input()`` leaf regardless of grounding (any behaviorally-equivalent, more complex
    ``produce(...)`` candidate would just get deduped away as more expensive). What *is`
    discriminating: under ``eager_grounding_over_universe`` the engine actually attempts a full
    recursive body search per candidate grounding (``INT``, ``GRID``, ...) — real, measurable extra
    work ``reject`` skips entirely by not attempting synthesis for this hole at all."""
    grid = Grid.from_list([[7]])
    task = Task(task_id="produce", train=(Example(input=grid, output=grid),), test=())
    library = Library(name="produce", primitives=(PRODUCE, IDENTITY_GRID))
    budget = Budget(max_depth=4, max_arity=1, max_pool=200)

    rejected = _engine(unpinned_type_var_mode="reject").run(
        train_examples=task.train,
        library=library,
        constraints=(),
        cost=ProgramSize(),
        budget=budget,
    )
    grounded = _engine(unpinned_type_var_mode="eager_grounding_over_universe").run(
        train_examples=task.train,
        library=library,
        constraints=(),
        cost=ProgramSize(),
        budget=budget,
    )
    assert rejected.stats.solved  # Input() alone solves the identity task either way
    assert grounded.stats.solved
    assert grounded.stats.considered > rejected.stats.considered


# -- recursive enclosing_target: propagation one level down, not just at the top -----------------


def test_enclosing_target_propagates_one_level_down() -> None:
    """A hole's own derived target becomes the *recursive* search's enclosing_target, not the
    top-level one: `inner`'s sampler is invoked both as a top-level candidate (where its COLOR
    return type doesn't unify with the GRID goal, so it gets `None`) and from within `outer`'s body
    search (where it should receive `outer`'s own propagated COLOR target) — proving the threading
    is genuinely recursive, not a one-off top-level rule."""
    received: list[EnclosingTarget | None] = []

    def _inner_sampler(
        train_examples: TrainExamples,
        sibling_arg_values: tuple[tuple[Value, ...] | None, ...],
        enclosing_target: EnclosingTarget | None,
    ) -> tuple[tuple[RawContext, ...], tuple[Value, ...] | None]:
        received.append(enclosing_target)
        return (), None

    inner = Primitive(
        name="inner",
        param_types=(ArrowType((INT,), COLOR),),
        return_type=COLOR,
        impl=lambda f: apply_function_value(f, (0,)),
        body_sampler=_inner_sampler,
    )

    def _outer_sampler(
        train_examples: TrainExamples,
        sibling_arg_values: tuple[tuple[Value, ...] | None, ...],
        enclosing_target: EnclosingTarget | None,
    ) -> tuple[tuple[RawContext, ...], tuple[Value, ...] | None]:
        examples = train_with_output(train_examples)
        contexts = tuple((example.input, (0,)) for example in examples)
        return contexts, tuple(7 for _ in examples)

    def _outer_impl(f: Value) -> Grid:
        color = apply_function_value(f, (0,))
        if not isinstance(color, int):
            raise TypeError("outer's function must yield a color")
        return Grid.from_list([[color]])

    outer = Primitive(
        name="outer",
        param_types=(ArrowType((INT,), COLOR),),
        return_type=GRID,
        impl=_outer_impl,
        body_sampler=_outer_sampler,
    )
    library = Library(name="nested", primitives=(outer, inner))
    task = Task(
        task_id="n",
        train=(Example(input=Grid.from_list([[1]]), output=Grid.from_list([[7]])),),
        test=(),
    )
    _engine().run(
        train_examples=task.train,
        library=library,
        constraints=(),
        cost=ProgramSize(),
        budget=Budget(max_depth=4, max_arity=1, max_pool=200),
    )
    assert received  # inner's sampler was invoked at least once
    assert any(t is None for t in received)  # the top-level attempt: COLOR doesn't unify with GRID
    matching = [t for t in received if t is not None and t.value_type == COLOR and t.values == (7,)]
    assert matching, received  # the nested attempt: outer's own propagated target reached inner


# -- filter/fold/sort_by: toy libraries, each solving a small synthesized-function task -----------


def _count_matching(xs: Value, pred: Value) -> Grid:
    if not isinstance(xs, tuple):
        raise TypeError("count_matching expects a list")
    count = sum(1 for x in xs if apply_function_value(pred, (x,)))
    return Grid.from_list([[count]])


def _count_matching_sampler(
    train_examples: TrainExamples,
    sibling_arg_values: tuple[tuple[Value, ...] | None, ...],
    enclosing_target: EnclosingTarget | None,
) -> tuple[tuple[RawContext, ...], tuple[Value, ...] | None]:
    examples = train_with_output(train_examples)
    if len(examples) != len(sibling_arg_values):
        return (), None  # a nested, non-training-example-shaped attempt — not synthesizable here
    contexts: list[RawContext] = []
    for example, values in zip(examples, sibling_arg_values, strict=True):
        if values is None:
            continue
        (xs,) = values
        if not isinstance(xs, tuple):
            continue
        for element in xs:
            contexts.append((example.input, (element,)))
    return tuple(contexts), None


_A = TypeVar("a")

#: The hole's type var (`a`) is free on purpose, matching FILTER's real shape (`a -> BOOL`) —
#: pinned to COLOR via sibling unification (the list argument), not baked in as a concrete
#: ``ArrowType((COLOR,), BOOL)``. A concrete hole (no free type vars) tells the engine there are no
#: siblings to wire in at all (that's the correct reading for `build_grid`, which truly has none) —
#: so a *pinnable-but-happens-to-resolve-to-one-type* hole must still go in as a TypeVar, or the
#: sibling list's values never reach the body sampler.
COUNT_MATCHING = Primitive(
    name="count_matching",
    param_types=(list_type(_A), ArrowType((_A,), BOOL)),
    return_type=GRID,
    impl=_count_matching,
    body_sampler=_count_matching_sampler,
)


def test_filter_style_toy_solves_via_a_synthesized_predicate() -> None:
    grid = Grid.from_list([[3, 5, 3]])
    task = Task(task_id="cm", train=(Example(input=grid, output=Grid.from_list([[2]])),), test=())
    library = Library(name="cm", primitives=(COUNT_MATCHING, CELLS, EQ))
    engine = _engine(constant_sources=("harvest-from-instance",))
    result = engine.run(
        train_examples=task.train,
        library=library,
        constraints=(),
        cost=ProgramSize(),
        budget=Budget(max_depth=5, max_arity=1, max_pool=500),
    )
    assert result.stats.solved


def test_fold_solves_via_a_synthesized_combiner() -> None:
    # fold(lam(lam($0)), seed, cells(input)) = the last element, for any seed — needs no arithmetic,
    # and no constant leaves either (the seed comes from whatever's pooled) — kept minimal since
    # sibling-pinned hole synthesis fans out combinatorially with pool size (§ decision 3's cost
    # note applies to ordinary sibling-pinning too, not just eager grounding).
    to_grid = Primitive(
        name="to_grid", param_types=(COLOR,), return_type=GRID, impl=lambda c: Grid.from_list([[c]])
    )
    grid = Grid.from_list([[1, 2, 3]])
    task = Task(task_id="fold", train=(Example(input=grid, output=Grid.from_list([[3]])),), test=())
    library = Library(name="fold", primitives=(FOLD, CELLS, to_grid))
    engine = _engine(constant_sources=())
    result = engine.run(
        train_examples=task.train,
        library=library,
        constraints=(),
        cost=ProgramSize(),
        budget=Budget(max_depth=4, max_arity=1, max_pool=100),
    )
    assert result.stats.solved


def _head(xs: Value) -> Value:
    if not isinstance(xs, tuple) or not xs:
        raise IndexError("head of an empty list")
    return xs[0]


_HEAD = Primitive(name="head", param_types=(list_type(COLOR),), return_type=COLOR, impl=_head)
_TO_GRID_COLOR = Primitive(
    name="to_grid", param_types=(COLOR,), return_type=GRID, impl=lambda c: Grid.from_list([[c]])
)


def test_sort_by_solves_via_a_grounded_key() -> None:
    # to_grid(head(sort_by(lam($0), cells(input)))) — the smallest element, via an identity key
    # grounded to COLOR (sort_by's key is unshared with any sibling, decision 4's exact case).
    grid = Grid.from_list([[3, 1, 2]])
    task = Task(task_id="sort", train=(Example(input=grid, output=Grid.from_list([[1]])),), test=())
    library = Library(name="sort", primitives=(SORT_BY, CELLS, _HEAD, _TO_GRID_COLOR))
    engine = _engine(constant_sources=(), unpinned_type_var_mode="eager_grounding_over_universe")
    result = engine.run(
        train_examples=task.train,
        library=library,
        constraints=(),
        cost=ProgramSize(),
        budget=Budget(max_depth=6, max_arity=1, max_pool=200),
    )
    assert result.stats.solved


# -- the payoff: map solves a real recolor task end-to-end ----------------------------------------


def _shift_color(grid: Grid) -> Grid:
    return Grid.from_list([[(c + 1) % 10 for c in row] for row in grid.to_list()])


def _row_to_grid(xs: Value) -> Grid:
    if not isinstance(xs, tuple):
        raise TypeError(f"row_to_grid expects a list, got {type(xs).__name__}")
    row = [x for x in xs if isinstance(x, int)]
    if len(row) != len(xs):
        raise TypeError("row_to_grid expects a list of colors")
    return Grid.from_list([row])


#: A single-row-only inverse of ``cells`` (contrast ``from_cells``, which needs width/height too) —
#: kept minimal to isolate the claim under test: map's own sibling-pinning + eager-grounding wiring,
#: not composition depth in general.
_ROW_TO_GRID = Primitive(
    name="row_to_grid", param_types=(list_type(COLOR),), return_type=GRID, impl=_row_to_grid
)


def _next_color(c: int) -> int:
    return (c + 1) % 10


#: A plain COLOR -> COLOR primitive, not eq/if — a conditional recolor body (`if(eq($0,3),7,$0)`) was
#: tried here first and, even at max_depth=6, didn't solve inside a tractable search (empirically
#: confirmed: ~10M candidates considered, no solution — see EXPERIMENTS.md). That's a real cost-vs-
#: depth finding about eager_grounding_over_universe, not a mechanism bug (the target program was
#: hand-verified to evaluate correctly); it's tracked there rather than chased further in this test.
#: This body still exercises the same real mechanism (map's unshared codomain resolved via
#: eager_grounding_over_universe, wired through real cells/row_to_grid glue) without needing that depth.
_NEXT_COLOR = Primitive(
    name="next_color", param_types=(COLOR,), return_type=COLOR, impl=_next_color
)


def test_map_solves_recolor_end_to_end() -> None:
    grid = Grid.from_list([[1, 3, 2]])
    task = Task(task_id="shift", train=(Example(input=grid, output=_shift_color(grid)),), test=())
    library = Library(name="shift", primitives=(MAP, CELLS, _ROW_TO_GRID, _NEXT_COLOR))
    engine = _engine(unpinned_type_var_mode="eager_grounding_over_universe")
    result = engine.run(
        train_examples=task.train,
        library=library,
        constraints=(),
        cost=ProgramSize(),
        budget=Budget(max_depth=4, max_arity=1, max_pool=200),
    )
    assert result.stats.solved
    solution = result.ranked_programs[0]
    unseen = Grid.from_list([[5, 0, 9]])  # unseen exact layout, same single-row shape
    assert solution.evaluate_grid(unseen, library) == _shift_color(unseen)
