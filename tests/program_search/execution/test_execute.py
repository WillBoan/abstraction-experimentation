"""``execute``: the recorded-run core — idempotency, resume, error isolation, artifacts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from arc_lab.core.dataset import Corpus
from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task, TrainExamples
from arc_lab.program_search.execution.execute import execute
from arc_lab.program_search.execution.model import Config, RunSpec
from arc_lab.program_search.execution.model.run_record import considered_total
from arc_lab.program_search.execution.model.trace_spec import TraceSpec
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.constraints import Constraint
from arc_lab.program_search.search.cost import Cost
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine, SearchEngine
from arc_lab.program_search.search.search_result import SearchResult, SearchStats
from arc_lab.program_search.search.tracking import SampleSpec, SearchTracker
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.program_search.substrate.types import GRID, Type

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
        unpinned_type_var_mode="reject",
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
        goal_type: Type | None = GRID,
        tracker: SearchTracker | None = None,
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
        goal_type: Type | None = GRID,
        tracker: SearchTracker | None = None,
    ) -> SearchResult:
        raise RuntimeError("search exploded")


def test_execute_end_to_end_search_run(tmp_path: Path) -> None:
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=_real_engine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    record = execute(spec, runs_root=tmp_path)

    assert record.completed
    assert record.run_dir.parent.parent == tmp_path  # grouped under a <date> subfolder
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", record.run_dir.parent.name)
    assert record.run_dir.name.endswith(f"_{spec.run_id}")
    runspec = json.loads(record.runspec_path.read_text())
    assert runspec["run_id"] == spec.run_id
    assert runspec["corpus_name"] == "exec-test"
    assert isinstance(runspec["run_started_at"], str) and runspec["run_started_at"]

    results = record.results()
    assert results["task_count"] == 1
    assert results["solved"] == 1
    total = considered_total(results)
    assert isinstance(total, int) and total > 0
    search_stats = results["search_stats"]
    assert isinstance(search_stats, dict)
    assert isinstance(search_stats["total"], dict) and isinstance(
        search_stats["by_primitive"], dict
    )

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


def test_execute_cache_hits_a_legacy_flat_run_dir(tmp_path: Path) -> None:
    """A run recorded before date-grouping (flat ``runs/<dir>``) still resolves as a cache hit —
    no re-execution, no duplicate nested copy."""
    CountingEngine.calls.clear()
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=CountingEngine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    record = execute(spec, runs_root=tmp_path)
    assert len(CountingEngine.calls) == 1
    # relocate the run dir up one level, simulating the pre-grouping flat layout
    flat_dir = tmp_path / record.run_dir.name
    record.run_dir.rename(flat_dir)
    record.run_dir.parent.rmdir()  # remove the now-empty <date> folder

    again = execute(spec, runs_root=tmp_path)
    assert len(CountingEngine.calls) == 1, "the flat legacy dir must be found, not re-run"
    assert again.run_dir == flat_dir


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


# -- TraceSpec: default sampling, full capture, capture summary ----------------------------


def test_execute_default_trace_writes_samples(tmp_path: Path) -> None:
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=_real_engine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    record = execute(spec, runs_root=tmp_path)  # no explicit trace: the default sampler applies
    rows = record.sample_rows()
    assert rows is not None and rows  # JSONL flat rows
    assert all(
        {"task", "candidate_index", "primitive", "outcome", "program"} <= row.keys() for row in rows
    )
    assert all(row["task"] == "t1" for row in rows)
    assert all(isinstance(row["program"], str) for row in rows)  # readable strings, not dicts
    assert not record.capture_summary_path.is_file()  # capture_all was never requested


def test_execute_no_sampling_writes_no_samples(tmp_path: Path) -> None:
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=_real_engine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    record = execute(spec, runs_root=tmp_path, trace=TraceSpec(samples=()))
    assert record.sample_rows() is None


def _per_task_summary(summary: dict[str, object], task_id: str) -> dict[str, object]:
    per_task = summary["per_task"]
    assert isinstance(per_task, dict)
    entry = per_task[task_id]
    assert isinstance(entry, dict)
    return entry


def test_execute_track_all_writes_capture_and_summary(tmp_path: Path) -> None:
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=_real_engine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    record = execute(spec, runs_root=tmp_path, trace=TraceSpec(capture_all=True))
    capture_file = record.capture_dir / "t1.jsonl"
    assert capture_file.is_file()
    captured_rows = [json.loads(line) for line in capture_file.read_text().splitlines()]
    assert captured_rows, "at least one considered candidate must be captured"
    assert all(isinstance(row["program"], str) for row in captured_rows)  # readable strings
    # Written in generation order: the first N candidates by index, contiguous from 0, no gaps.
    assert [row["candidate_index"] for row in captured_rows] == list(range(len(captured_rows)))
    summary = record.capture_summary()
    assert summary is not None
    assert summary["truncated"] is False
    assert _per_task_summary(summary, "t1")["captured"] == len(captured_rows)


def test_execute_profile_writes_summary_and_stats(tmp_path: Path) -> None:
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=_real_engine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    record = execute(spec, runs_root=tmp_path, trace=TraceSpec(profile=True))
    assert record.profile_stats_path.is_file()  # raw pstats dump for later exploration
    summary = record.profile_summary()
    assert summary is not None
    assert "total profiled wall time" in summary
    assert "phase rollup" in summary
    assert "evaluation: compute_signature" in summary  # a load-bearing phase anchor is attributed


def test_execute_without_profile_writes_no_profile_artifacts(tmp_path: Path) -> None:
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=_real_engine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    record = execute(spec, runs_root=tmp_path)  # default TraceSpec: profiling off
    assert not record.profile_dir.exists()
    assert record.profile_summary() is None


def test_execute_track_all_max_truncates_loudly(tmp_path: Path) -> None:
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=_real_engine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    record = execute(spec, runs_root=tmp_path, trace=TraceSpec(capture_all=True, capture_all_max=1))
    summary = record.capture_summary()
    assert summary is not None
    assert summary["truncated"] is True
    task_summary = _per_task_summary(summary, "t1")
    assert task_summary["captured"] == 1
    considered = task_summary["considered"]
    assert isinstance(considered, int) and considered > 1  # more considered than captured


def test_execute_sample_rows_are_flat_and_bucketed(tmp_path: Path) -> None:
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=_real_engine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    record = execute(
        spec, runs_root=tmp_path, trace=TraceSpec(samples=(SampleSpec(k=1, mode="first_k"),))
    )
    rows = record.sample_rows()
    assert rows is not None and rows
    # one row per (primitive, outcome) bucket, at most k=1 program each
    buckets = [(row["primitive"], row["outcome"]) for row in rows]
    assert len(buckets) == len(set(buckets))


def test_force_recapture_reexecutes_a_cached_run(tmp_path: Path) -> None:
    CountingEngine.calls.clear()
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=CountingEngine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    execute(spec, runs_root=tmp_path)
    assert len(CountingEngine.calls) == 1
    execute(spec, runs_root=tmp_path)  # ordinary cache hit: no re-execution
    assert len(CountingEngine.calls) == 1
    execute(spec, runs_root=tmp_path, force_recapture=True)
    assert len(CountingEngine.calls) == 2, "force_recapture must re-execute a completed run"


def test_resume_preserves_pre_crash_samples(tmp_path: Path) -> None:
    """``samples.jsonl`` must cover every task, not just the batch a resume re-ran — otherwise it
    silently disagrees with the complete ``trace.jsonl``/``results.json``."""
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=_real_engine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED), _flip_task("t2", _IN2, _FLIPPED2)),
    )
    first = execute(spec, runs_root=tmp_path)  # full run, default sampling
    assert {row["task"] for row in (first.sample_rows() or [])} == {"t1", "t2"}

    # simulate a crash after t1: drop results.json, truncate the trace to just t1's row
    rows = list(first.trace_rows())
    first.results_path.unlink()
    with first.trace_path.open("w", encoding="utf-8") as trace:
        trace.write(json.dumps(rows[0]) + "\n")

    resumed = execute(spec, runs_root=tmp_path)  # only t2 re-runs
    assert {row["task"] for row in (resumed.sample_rows() or [])} == {"t1", "t2"}


def test_force_recapture_clears_stale_capture_artifacts(tmp_path: Path) -> None:
    """Turning capture off on a force_recapture must not leave the prior run's capture/ behind."""
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=_real_engine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    captured = execute(spec, runs_root=tmp_path, trace=TraceSpec(capture_all=True))
    assert (captured.capture_dir / "t1.jsonl").is_file()

    recaptured = execute(spec, runs_root=tmp_path, trace=TraceSpec(), force_recapture=True)
    assert not recaptured.capture_dir.exists()  # no stale capture tree from the prior TraceSpec
    assert recaptured.capture_summary() is None


def test_force_recapture_populates_tracing_on_an_already_completed_run(tmp_path: Path) -> None:
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=_real_engine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    record = execute(spec, runs_root=tmp_path)  # default trace: no full capture yet
    assert not record.capture_summary_path.is_file()

    recaptured = execute(
        spec, runs_root=tmp_path, trace=TraceSpec(capture_all=True), force_recapture=True
    )
    assert recaptured.run_id == record.run_id
    assert recaptured.capture_summary_path.is_file()
    assert (recaptured.capture_dir / "t1.jsonl").is_file()
    assert recaptured.results()["solved"] == 1  # substantive content is unchanged by recapture


def test_execute_writes_run_log(tmp_path: Path) -> None:
    """``run.log`` is always populated on a fresh run — independent of any console verbosity
    configuration, since ``_run_log_handler`` bumps the logger's own level for the run's duration."""
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=_real_engine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    record = execute(spec, runs_root=tmp_path)

    assert record.log_path.is_file()
    contents = record.log_path.read_text(encoding="utf-8")
    assert contents.strip(), "run.log must not be empty"
    assert f"recorded to {record.run_dir}" in contents  # execute()'s own completion line
    assert "task=t1" in contents  # the per-task search's progress lines carry the task id


def test_execute_cache_hit_does_not_error_with_an_existing_run_log(tmp_path: Path) -> None:
    spec = RunSpec(
        config=Config(library=D4_LIBRARY, search_engine=_real_engine(), budget=_BUDGET),
        corpus=_corpus(_flip_task("t1", _IN, _FLIPPED)),
    )
    execute(spec, runs_root=tmp_path)
    record = execute(spec, runs_root=tmp_path)  # cache hit: no re-execution, no new handler setup
    assert record.completed
    assert record.log_path.is_file()  # left over from the first, non-cached execution
