"""Commit-2 telemetry: sleep-cost counters thread run -> select -> propose -> LearnOutcome."""

from __future__ import annotations

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.program_search.analysis.compression import SolvedTask
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.learn.telemetry import SleepCounters
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.program import Apply, Input, Program

_GRID = Grid.from_list([[1, 2], [3, 4]])
_ROT180: Program = Apply("rot90", (Apply("rot90", (Input(),)),))
_A: Program = Apply("flip_h", (_ROT180,))
_B: Program = Apply("flip_v", (_ROT180,))


def _solved(program: Program, task_id: str) -> SolvedTask:
    task = Task(task_id=task_id, train=(Example(input=_GRID, output=_GRID),), test=())
    return SolvedTask(annotated=AnnotatedTask(task, None), program=program)


def test_antiunify_pair_counter_counts_each_distinct_pair() -> None:
    counters = SleepCounters()
    AntiunifyPairs().propose([_A, _B], D4_LIBRARY, counters=counters)
    assert counters.antiunify_pair_count == 1  # exactly one distinct pair, counted before filtering
    assert counters.proposal_count == 0  # propose never touches proposal_count (the selector does)


def test_learn_outcome_carries_sleep_costs() -> None:
    # Two identical solved programs: the verbatim-recurrence path proposes a closed template,
    # so proposal_count > 0 threads all the way out onto the LearnOutcome.
    corpus = (_solved(_A, "a"), _solved(_A, "b"))
    outcome = GreedyMDLLearnEngine(proposer=AntiunifyPairs()).run(D4_LIBRARY, corpus)
    assert outcome.proposal_count > 0
    assert outcome.antiunify_pair_count == 0  # never two distinct programs, so no pairs
