"""Capability tracking: ``primitive_keys``, ``SearchTracker``, and the outcome-partition invariant
(every considered candidate resolves to exactly one ``Outcome`` — ``considered == sum(outcomes)``).
"""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task, TrainExamples
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.constraints import Constraint
from arc_lab.program_search.search.cost import ProgramSize
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.search.search_result import SearchResult
from arc_lab.program_search.search.tracking import (
    OUTCOME_NAMES,
    GenerationTracker,
    Outcome,
    SampleSpec,
    SearchTracker,
    primitive_keys,
)
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.program import (
    AppFn,
    Apply,
    Const,
    If,
    Input,
    Lam,
    PrimRef,
    Program,
    Var,
)
from arc_lab.program_search.substrate.types import BOOL, COLOR, GRID, INT

# -- primitive_keys: structural capability tags --------------------------------------------------


def test_primitive_keys_from_apply() -> None:
    program = Apply(primitive="rot90", args=(Input(),))
    assert primitive_keys(program) == frozenset({"rot90"})


def test_primitive_keys_from_primref() -> None:
    program = AppFn(fn=PrimRef(name="width"), args=(Input(),))
    assert primitive_keys(program) == frozenset({"width", "__appfn__"})


def test_primitive_keys_node_kind_pseudo_keys() -> None:
    cond = Const(value=True, value_type=BOOL)
    program = If(cond=cond, then=Input(), orelse=Input())
    assert primitive_keys(program) == frozenset({"__if__", "__const__"})


def test_primitive_keys_walks_nested_lambda_body() -> None:
    body = Apply(
        primitive="add", args=(Var(index=0, value_type=INT), Const(value=1, value_type=INT))
    )
    program = Lam(param_type=INT, body=body)
    assert primitive_keys(program) == frozenset({"__lam__", "add", "__const__"})


# -- SearchTracker: the accumulator --------------------------------------------------------------


def test_tracker_totals_are_funnel_ordered_with_zeros() -> None:
    tracker = SearchTracker()
    tracker.considered += 2
    tracker.record(0, Input(), frozenset({"rot90"}), Outcome.ACCEPTED)
    tracker.record(1, Input(), frozenset({"rot90", "__if__"}), Outcome.PRUNED)
    totals = tracker.totals()
    assert totals["accepted"] == 1 and totals["pruned"] == 1
    assert totals["errored"] == 0  # zeros are filled — a stable, self-documenting schema
    assert list(totals) == list(OUTCOME_NAMES)  # funnel order
    assert tracker.considered == sum(totals.values())
    assert tracker.by_primitive()["rot90"] == {"pruned": 1, "accepted": 1}  # funnel order, sparse
    assert tracker.by_primitive()["__if__"] == {"pruned": 1}


def test_tracker_sample_rows_first_k_keeps_arrival_order() -> None:
    tracker = SearchTracker(samples=(SampleSpec(k=2, mode="first_k"),))
    programs = [Apply(primitive="rot90", args=(Input(),)) for _ in range(3)]
    for index, program in enumerate(programs):
        tracker.record(index, program, frozenset({"rot90"}), Outcome.PRUNED)
    rows = tracker.sample_rows()
    assert [row["candidate_index"] for row in rows] == [0, 1]  # first two kept, third over cap
    assert all(row == {**row, "primitive": "rot90", "outcome": "pruned"} for row in rows)
    assert rows[0]["program"] == "rot90(input)"  # a readable string, not a dict


def test_tracker_sample_rows_cheapest_k_keeps_the_smallest() -> None:
    tracker = SearchTracker(samples=(SampleSpec(k=1, mode="cheapest_k"),))
    large = Apply(primitive="rot90", args=(Apply(primitive="rot90", args=(Input(),)),))
    small = Apply(primitive="rot90", args=(Input(),))
    tracker.record(0, large, frozenset({"rot90"}), Outcome.PRUNED)
    tracker.record(1, small, frozenset({"rot90"}), Outcome.PRUNED)  # smaller, arrives second
    rows = tracker.sample_rows()
    assert [row["candidate_index"] for row in rows] == [1]
    assert rows[0]["program"] == "rot90(input)"


def test_tracker_capture_sink_is_called_for_every_record() -> None:
    seen: list[tuple[int, str, str]] = []
    tracker = SearchTracker(
        capture=lambda index, program, primitives, outcome: seen.append(
            (index, str(program), outcome.value)
        )
    )
    tracker.record(0, Input(), frozenset({"rot90"}), Outcome.ACCEPTED)
    tracker.record(1, Input(), frozenset(), Outcome.ERRORED)
    assert seen == [(0, "input", "accepted"), (1, "input", "errored")]


# -- end-to-end: the outcome partition through a real search ------------------------------------
#
# One library engineered so a single run exercises six of the eight outcomes:
#   transpose      -> the solution                                  -> ACCEPTED
#   transpose2      (same impl, same cost, absorbed after transpose) -> DEDUPED
#   boom            (raises on every context)                        -> ERRORED
#   lie_about_type  (declared COLOR, actually returns a Grid)        -> PRUNED
#   flip_h          (pooled, then truncated by a tight max_pool)     -> EVICTED
#   Input           (the round-0 leaf, never matches the target)     -> GOAL_UNMATCHED
# DISPLACED is covered at the Pool level (test_pool.py); forcing it through a full engine run
# would need a contrived cost/ordering setup that adds little beyond that unit test.

_GRID = Grid.from_list([[1, 2], [3, 4]])


def _transpose(grid: Grid) -> Grid:
    return Grid.from_list([list(col) for col in zip(*grid.to_list(), strict=True)])


def _flip_h(grid: Grid) -> Grid:
    return Grid.from_list([list(reversed(row)) for row in grid.to_list()])


def _boom(grid: Grid) -> Grid:
    raise RuntimeError("boom")


def _lie_about_type(grid: Grid) -> Grid:
    return grid  # declared COLOR below — deliberately the wrong runtime type, for PRUNED


_TRANSPOSE = Primitive(name="transpose", param_types=(GRID,), return_type=GRID, impl=_transpose)
_TRANSPOSE2 = Primitive(name="transpose2", param_types=(GRID,), return_type=GRID, impl=_transpose)
_FLIP_H = Primitive(name="flip_h", param_types=(GRID,), return_type=GRID, impl=_flip_h)
_BOOM = Primitive(name="boom", param_types=(GRID,), return_type=GRID, impl=_boom)
_LIE = Primitive(
    name="lie_about_type", param_types=(GRID,), return_type=COLOR, impl=_lie_about_type
)

_LIBRARY = Library(name="outcomes", primitives=(_TRANSPOSE, _TRANSPOSE2, _BOOM, _LIE, _FLIP_H))

_ENGINE = BottomUpSearchEngine(
    constant_sources=(),
    function_hole_fill_mode="none",
    polymorphism_instantiation="monomorphize",
    unpinned_type_var_mode="reject",
)

_BUDGET = Budget(depth_limit=1, max_arity=1, max_pool=2)


class _RejectAll(Constraint):
    """A test constraint: rejects every candidate."""

    def holds(self, program: Program, train_examples: TrainExamples, library: Library) -> bool:
        return False


def _run(constraints: tuple[Constraint, ...] = ()) -> SearchResult:
    task = Task(task_id="t", train=(Example(input=_GRID, output=_transpose(_GRID)),), test=())
    return _ENGINE.run(
        train_examples=task.train,
        library=_LIBRARY,
        constraints=constraints,
        cost=ProgramSize(),
        budget=_BUDGET,
    )


def test_outcome_partition_invariant_holds() -> None:
    result = _run()
    outcomes = result.stats.outcomes
    assert result.stats.considered == sum(outcomes.values())


def test_each_engineered_outcome_is_exercised() -> None:
    result = _run()
    outcomes = result.stats.outcomes
    assert outcomes["errored"] == 1  # boom
    assert outcomes["pruned"] == 1  # lie_about_type
    assert outcomes["deduped"] == 1  # transpose2
    assert outcomes["evicted"] == 1  # flip_h, truncated by max_pool=2
    assert outcomes["goal_unmatched"] == 1  # the Input leaf
    assert outcomes["accepted"] == 1  # transpose
    assert result.stats.accepted == 1


def test_by_primitive_attributes_outcomes_to_the_right_primitive() -> None:
    result = _run()
    by_primitive = result.stats.by_primitive
    assert by_primitive["boom"] == {"errored": 1}
    assert by_primitive["lie_about_type"] == {"pruned": 1}
    assert by_primitive["transpose2"] == {"deduped": 1}
    assert by_primitive["flip_h"] == {"evicted": 1}
    assert by_primitive["transpose"] == {"accepted": 1}


def test_constraint_rejected_when_the_solution_is_filtered() -> None:
    result = _run(constraints=(_RejectAll(),))
    outcomes = result.stats.outcomes
    assert outcomes.get("accepted", 0) == 0
    assert outcomes["constraint_rejected"] == 1
    assert result.ranked_programs == ()
    assert result.stats.considered == sum(outcomes.values())


# -- the new-layer restriction: each syntactic program is built once, not once per round --------

_GEO_LIBRARY = Library(name="geo", primitives=(_TRANSPOSE, _FLIP_H))


def test_new_layer_restriction_considers_each_program_once() -> None:
    """At ``depth_limit=2`` a naive enumerator that composes over the whole pool each round would
    regenerate every depth-1 program at depth 2 (and dedup it away), so the same syntactic program
    surfaces as several distinct considered candidates. The new-layer restriction composes only with
    the previous round's additions, so each distinct program is considered exactly once — a full
    capture holds no duplicate program string."""
    seen: list[str] = []
    tracker = SearchTracker(
        capture=lambda index, program, primitives, outcome: seen.append(str(program))
    )
    task = Task(task_id="t", train=(Example(input=_GRID, output=_transpose(_GRID)),), test=())
    BottomUpSearchEngine(
        constant_sources=(),
        function_hole_fill_mode="none",
        polymorphism_instantiation="monomorphize",
        unpinned_type_var_mode="reject",
    ).run(
        train_examples=task.train,
        library=_GEO_LIBRARY,
        constraints=(),
        cost=ProgramSize(),
        budget=Budget(depth_limit=2, max_arity=1, max_pool=100),
        tracker=tracker,
    )
    assert seen, "the search must consider candidates"
    assert len(seen) == len(set(seen)), "no syntactic program is regenerated across rounds"
    # A depth-1 program is formed once at round 1 and never re-formed when it is a leaf-only
    # composition at round 2 (which is exactly what the restriction suppresses).
    assert seen.count("transpose(input)") == 1


# -- GenerationTracker: the per-round summary, Outcome-free and separate from _totals -------------


def test_generation_tracker_defaults_to_zero() -> None:
    gen_tracker = GenerationTracker()
    assert gen_tracker.pool_size_start == 0
    assert gen_tracker.pool_size_before_truncation is None
    assert gen_tracker.pool_size_end is None
    assert gen_tracker.composed == gen_tracker.errored == gen_tracker.pruned == 0
    assert gen_tracker.deduped == gen_tracker.entered_pool == 0
    assert gen_tracker.displaced == gen_tracker.evicted == 0


def test_record_with_generation_bumps_the_matching_field_and_composed() -> None:
    tracker = SearchTracker()
    tracker.begin_generation(pool_size_start=10)
    tracker.record(0, Input(), frozenset(), Outcome.ERRORED, generation=0)
    tracker.record(1, Input(), frozenset(), Outcome.PRUNED, generation=0)
    tracker.record(2, Input(), frozenset(), Outcome.DEDUPED, generation=0)
    gen_tracker = tracker.generation_at(0)
    assert (gen_tracker.errored, gen_tracker.pruned, gen_tracker.deduped) == (1, 1, 1)
    assert gen_tracker.composed == 3  # errored + pruned + deduped, all counted


def test_record_displaced_bumps_displaced_but_not_composed() -> None:
    """Displacement isn't part of `composed` (invariant: composed == errored + pruned + deduped +
    entered_pool) — a displaced entry was already counted as `entered_pool` when it was first
    absorbed, so counting it again here would double-count it."""
    tracker = SearchTracker()
    tracker.begin_generation(pool_size_start=0)
    tracker.record(0, Input(), frozenset(), Outcome.DISPLACED, generation=0)
    gen_tracker = tracker.generation_at(0)
    assert gen_tracker.displaced == 1
    assert gen_tracker.composed == 0


def test_record_without_generation_does_not_touch_generations_but_still_updates_totals() -> None:
    tracker = SearchTracker()
    tracker.begin_generation(pool_size_start=0)
    tracker.record(0, Input(), frozenset({"rot90"}), Outcome.ERRORED)  # generation=None (default)
    assert tracker.totals()["errored"] == 1
    assert tracker.generation_at(0).errored == 0  # untouched


def test_record_of_whole_run_outcomes_is_excluded_from_generation_tracking() -> None:
    """ACCEPTED/GOAL_UNMATCHED/CONSTRAINT_REJECTED are only ever recorded once, at whole-run
    extraction after every round has finished — there's no live "current round" for them, so
    even if a caller passed `generation=`, `GenerationTracker` must stay untouched."""
    tracker = SearchTracker()
    tracker.begin_generation(pool_size_start=0)
    tracker.record(0, Input(), frozenset(), Outcome.ACCEPTED, generation=0)
    tracker.record(1, Input(), frozenset(), Outcome.GOAL_UNMATCHED, generation=0)
    tracker.record(2, Input(), frozenset(), Outcome.CONSTRAINT_REJECTED, generation=0)
    gen_tracker = tracker.generation_at(0)
    assert gen_tracker.composed == 0
    assert tracker.totals()["accepted"] == 1  # still landed in the whole-run totals


def test_mark_entered_pool_bumps_entered_pool_and_composed() -> None:
    tracker = SearchTracker()
    tracker.begin_generation(pool_size_start=0)
    tracker.mark_entered_pool(0)
    tracker.mark_entered_pool(0)
    gen_tracker = tracker.generation_at(0)
    assert gen_tracker.entered_pool == 2
    assert gen_tracker.composed == 2


def test_mark_entered_pool_is_a_no_op_for_none() -> None:
    tracker = SearchTracker()
    tracker.mark_entered_pool(None)  # a lambda-synthesis sub-search's own absorption — no crash


def test_begin_end_generation_track_pool_size_snapshots_per_round() -> None:
    tracker = SearchTracker()
    tracker.begin_generation(pool_size_start=1)
    tracker.mark_pool_size_before_truncation(0, 40)
    tracker.end_generation(0, 12)
    tracker.begin_generation(pool_size_start=12)
    tracker.mark_pool_size_before_truncation(1, 90)
    tracker.end_generation(1, 20)
    round0 = tracker.generation_at(0)
    assert (round0.pool_size_start, round0.pool_size_before_truncation, round0.pool_size_end) == (
        1,
        40,
        12,
    )
    round1 = tracker.generation_at(1)
    assert (round1.pool_size_start, round1.pool_size_before_truncation, round1.pool_size_end) == (
        12,
        90,
        20,
    )
