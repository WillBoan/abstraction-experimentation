"""Tests for the propose -> filter -> rank building blocks: Constraint and Cost."""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search import (
    ConsistentWithTraining,
    Constraint,
    ProgramSize,
    SingleApply,
)
from arc_lab.solvers.dsl.search.base import Search, SearchResult, SearchStats
from arc_lab.solvers.dsl.solver import ProgramSearchSolver
from arc_lab.solvers.dsl.substrate import Apply, Input, Library, Program
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY

_G = Grid.from_list


def _flip_task() -> Task:
    return Task.from_dict(
        "flip",
        {
            "train": [{"input": [[1, 2, 3]], "output": [[3, 2, 1]]}],
            "test": [{"input": [[4, 5, 6]], "output": [[6, 5, 4]]}],
        },
    )


# -- Constraint (the filter step) ---------------------------------------


def test_consistent_with_training_accepts_and_rejects() -> None:
    task = _flip_task()
    assert ConsistentWithTraining().holds(Apply("flip_h", (Input(),)), task, D4_LIBRARY) is True
    assert ConsistentWithTraining().holds(Apply("rot90", (Input(),)), task, D4_LIBRARY) is False


class _RejectAll(Constraint):
    def holds(self, program: Program, task: Task, library: Library) -> bool:
        return False


def test_constraints_compose_all_must_hold() -> None:
    task = _flip_task()
    # Baseline: the default (consistency) constraint accepts flip_h.
    assert SingleApply().find(task, D4_LIBRARY).programs
    # Adding a reject-all constraint makes the same search find nothing.
    blocked = SingleApply(constraints=[ConsistentWithTraining(), _RejectAll()])
    assert blocked.find(task, D4_LIBRARY).programs == ()


# -- Cost (the rank step) -----------------------------------------------


def test_program_size_cost() -> None:
    task = _flip_task()
    assert ProgramSize().of(Input(), task, D4_LIBRARY) == 1.0
    assert ProgramSize().of(Apply("flip_h", (Input(),)), task, D4_LIBRARY) == 2.0


class _StubSearch(Search):
    """A search that returns fixed programs, to isolate the solver's ranking."""

    def __init__(self, programs: list[Program]) -> None:
        super().__init__()
        self._programs = programs

    def find(self, task: Task, library: Library) -> SearchResult:
        programs = tuple(self._programs)
        return SearchResult(
            programs=programs,
            stats=SearchStats(strategy="StubSearch", returned=len(programs)),
        )


def test_solver_ranks_candidates_by_cost() -> None:
    # The stub yields the bigger program first; the size cost must reorder so the
    # smaller program's output is the top-ranked candidate.
    big: Program = Apply("rot180", (Input(),))  # size 2
    small: Program = Input()  # size 1
    task = Task.from_dict(
        "t",
        {
            "train": [{"input": [[1, 2]], "output": [[1, 2]]}],
            "test": [{"input": [[3, 4]], "output": [[3, 4]]}],
        },
    )
    solver = ProgramSearchSolver(library=D4_LIBRARY, search=_StubSearch([big, small]), name="stub")
    prediction = solver.predict(task)
    # For test input [[3, 4]]: small (identity) -> [[3, 4]]; big (rot180) -> [[4, 3]].
    # Ranked smallest-first, the top candidate must be the identity output.
    assert prediction[0][0] == _G([[3, 4]])
