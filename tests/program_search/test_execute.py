"""``execute``: the recorded-run core — idempotency, resume, error isolation, artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from arc_lab.core.dataset import Corpus
from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task, TrainExamples
from arc_lab.program_search.execution.execute import execute
from arc_lab.program_search.execution.model import Config, RunSpec
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.constraints import Constraint
from arc_lab.program_search.search.cost import Cost
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine, SearchEngine
from arc_lab.program_search.search.search_result import SearchResult, SearchStats
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY

_IN = Grid.from_list([[1, 2], [3, 4]])
_FLIPPED = Grid.from_list([[2, 1], [4, 3]])
_IN2 = Grid.from_list([[5, 6], [7, 8]])
_FLIPPED2 = Grid.from_list([[6, 5], [8, 7]])


def _flip_task(task_id: str, grid: Grid, flipped: Grid) -> Task:
    example = Example(input=grid, output=flipped)
    return Task(task_id=task_id, train=(example,), test=(example,))


def _corpus(*tasks: Task) -> Corpus:
    return Corpus.of("exec-test", list(tasks))


_BUDGET = Budget(max_depth=2, max_arity=2, max_pool=200)


def _real_engine() -> BottomUpSearchEngine:
    return BottomUpSearchEngine(
        constant_sources=(),
        function_hole_fill_mode="none",
        polymorphism_instantiation="monomorphize",
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class CountingEngine(SearchEngine):
    """Returns no programs; tallies calls on a class-level list (frozen-safe)."""

    calls: ClassVar[list[str]] = []

    def run(
        self,
        *,
        train_examples: TrainExamples,
        library: Library,
        constraints: tuple[Constraint, ...],
        cost: Cost,
        budget: Budget,
    ) -> SearchResult:
        CountingEngine.calls.append(str(train_examples[0].input.to_list()))
        return SearchResult(ranked_programs=(), stats=SearchStats(engine="CountingEngine"))


@dataclass(frozen=True, slots=True, kw_only=True)
class BoomEngine(SearchEngine):
    def run(
        self,
        *,
        train_examples: TrainExamples,
        library: Library,
        constraints: tuple[Constraint, ...],
        cost: Cost,
        budget: Budget,
    ) -> SearchResult:
        raise RuntimeError("search exploded")


def test_execute_end_to_end_search_run(tmp_path: Path) -> None:
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=_real_engine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    record = execute(spec, runs_root=tmp_path)

    assert record.completed
    assert record.run_dir == tmp_path / spec.run_id
    runspec = json.loads(record.runspec_path.read_text())
    assert runspec["run_id"] == spec.run_id
    assert runspec["corpus_name"] == "exec-test"

    results = record.results()
    assert results["task_count"] == 1
    assert results["solved"] == 1
    assert isinstance(results["considered_total"], int) and results["considered_total"] > 0

    (row,) = record.trace_rows()
    assert row["task_id"] == "t1"
    assert row["programs"], "the solving program must be recorded in the trace"
    (result,) = record.task_results()
    assert result.score.solved and result.error is None


def test_execute_is_idempotent(tmp_path: Path) -> None:
    CountingEngine.calls.clear()
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=CountingEngine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    execute(spec, runs_root=tmp_path)
    assert len(CountingEngine.calls) == 1
    record = execute(spec, runs_root=tmp_path)  # cache hit: no execution
    assert len(CountingEngine.calls) == 1
    assert record.completed


def test_execute_resumes_from_partial_trace_with_torn_line(tmp_path: Path) -> None:
    CountingEngine.calls.clear()
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=CountingEngine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED), _flip_task("t2", _IN2, _FLIPPED2)),
    )
    first = execute(spec, runs_root=tmp_path)
    assert len(CountingEngine.calls) == 2

    # simulate a crash after t1: results.json gone, trace = t1's row + a torn write
    rows = list(first.trace_rows())
    first.results_path.unlink()
    with first.trace_path.open("w", encoding="utf-8") as trace:
        trace.write(json.dumps(rows[0], sort_keys=True) + "\n")
        trace.write('{"task_id": "t2", "sco')  # torn final line

    record = execute(spec, runs_root=tmp_path)
    assert len(CountingEngine.calls) == 3, "only t2 re-runs; t1 is served from the trace"
    assert record.results()["task_count"] == 2
    assert [row["task_id"] for row in record.trace_rows()] == ["t1", "t2"]


def test_execute_isolates_a_broken_task(tmp_path: Path) -> None:
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=BoomEngine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    record = execute(spec, runs_root=tmp_path)
    assert record.completed
    (result,) = record.task_results()
    assert result.error is not None and "search exploded" in result.error
    assert result.score.solved is False
    assert record.results()["solved"] == 0
