"""Extraction (§5.8): the goal test that reads solutions off a built pool.

Because the pool dedups by ``(type, signature)``, at most one entry can equal a fixed ``target`` at a
fixed ``goal_type`` — so ``extract`` yields the single Occam-cheapest witness of the target behaviour,
or nothing.
"""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task, TrainExamples
from arc_lab.program_search.search.constraints import Constraint
from arc_lab.program_search.search.extraction import extract
from arc_lab.program_search.search.pool import Pool
from arc_lab.program_search.search.signature import BOTTOM
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.program import Const, Program
from arc_lab.program_search.substrate.types import COLOR, GRID, INT

_G = Grid.from_list([[1]])
_TASK = Task(task_id="t", train=(Example(input=_G, output=_G),), test=())
_LIB = Library(name="t", primitives=())
_A = Const(value=1, value_type=COLOR)
_B = Const(value=2, value_type=COLOR)


class _Only(Constraint):
    """A test constraint: accepts exactly one designated program."""

    def __init__(self, allowed: Program) -> None:
        self.allowed = allowed

    def holds(self, program: Program, train_examples: TrainExamples, library: Library) -> bool:
        return program is self.allowed


def test_extracts_the_program_whose_signature_equals_target() -> None:
    pool = Pool()
    pool.add_dedup(GRID, (7, 8), _A, 2.0)  # signature == target
    pool.add_dedup(GRID, (7, 9), _B, 1.0)  # different (cheaper) signature — not the target
    assert extract(pool, GRID, (7, 8), (), _TASK.train, _LIB) == (_A,)


def test_no_match_returns_empty() -> None:
    pool = Pool()
    pool.add_dedup(GRID, (7, 9), _B, 1.0)
    assert extract(pool, GRID, (7, 8), (), _TASK.train, _LIB) == ()


def test_wrong_goal_type_is_excluded() -> None:
    pool = Pool()
    pool.add_dedup(INT, (7, 8), _A, 1.0)  # right signature, wrong type
    assert extract(pool, GRID, (7, 8), (), _TASK.train, _LIB) == ()


def test_partial_signature_never_matches_a_total_target() -> None:
    pool = Pool()
    pool.add_dedup(GRID, (7, BOTTOM), _A, 1.0)  # partial: ⊥ at the second context
    assert extract(pool, GRID, (7, 8), (), _TASK.train, _LIB) == ()


def test_constraints_filter_survivors() -> None:
    pool = Pool()
    pool.add_dedup(GRID, (7, 8), _A, 1.0)  # the sole match
    assert (
        extract(pool, GRID, (7, 8), (_Only(_B),), _TASK.train, _LIB) == ()
    )  # constraint rejects it
    assert extract(pool, GRID, (7, 8), (_Only(_A),), _TASK.train, _LIB) == (
        _A,
    )  # constraint accepts it
