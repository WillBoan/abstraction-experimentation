"""The activities: run_search_learn (the wake-sleep loop through execute) + analyze_run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from arc_lab.core.dataset import Corpus
from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.program_search.execution.analyze_run import analyze_run
from arc_lab.program_search.execution.execute import execute
from arc_lab.program_search.execution.model import Config, LearnSpec, RunSpec
from arc_lab.program_search.execution.run_search import run_search
from arc_lab.program_search.execution.run_search_learn import run_search_learn
from arc_lab.program_search.learn.antiunify import AntiunifyPairs
from arc_lab.program_search.learn.engines import GreedyMDLLearnEngine
from arc_lab.program_search.search.budget import Budget
from arc_lab.program_search.search.search_engine import BottomUpSearchEngine
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.geometry import D4_LIBRARY

# rot180 deliberately absent: the tasks are only solvable as rot90∘rot90 (a 3-node
# composite), so the recurring composite is exactly what sleep should compress to abs0.
_LIBRARY = Library(
    name="d4-no-rot180",
    primitives=tuple(p for p in D4_LIBRARY.primitives if p.name in ("identity", "rot90", "flip_h")),
)


def _rot180_task(task_id: str, cells: list[list[int]]) -> Task:
    grid = Grid.from_list(cells)
    flipped = Grid(grid.array[::-1, ::-1])
    example = Example(input=grid, output=flipped)
    return Task(task_id=task_id, train=(example,), test=(example,))


_TRAIN = Corpus.of(
    "learn-train",
    [_rot180_task("t1", [[1, 2], [3, 4]]), _rot180_task("t2", [[5, 6], [7, 8]])],
)
_EVAL = Corpus.of("learn-eval", [_rot180_task("t3", [[9, 1], [2, 3]])])


def _learn_config(iterations: int = 3) -> Config:
    return Config(
        library=_LIBRARY,
        search_engine=BottomUpSearchEngine(
            constant_sources=(),
            function_hole_fill_mode="none",
            polymorphism_instantiation="monomorphize",
            unpinned_type_var_mode="reject",
        ),
        budget=Budget(depth_limit=2, max_arity=2, max_pool=200),
        learn=LearnSpec(
            learn_engine=GreedyMDLLearnEngine(proposer=AntiunifyPairs()),
            iterations=iterations,
        ),
    )


def test_run_search_learn_end_to_end(tmp_path: Path) -> None:
    result = run_search_learn(_learn_config(), _TRAIN, _EVAL, runs_root=tmp_path)

    # the learn run: mints the rot180 abstraction, converges on the second sleep
    learn_results = result.learn.results()
    assert learn_results["added"] == ["abs0"]
    assert learn_results["converged"] is True
    assert learn_results["iterations_run"] == 2
    grown = result.learn.learned_library()
    assert grown.get("abs0").template is not None

    # 3 distinct recorded runs (learn + train-usefulness + transfer)
    assert result.transfer is not None
    run_ids = {result.learn.run_id, result.train_usefulness.run_id, result.transfer.run_id}
    assert len(run_ids) == 3

    # the derived SEARCH runs solve with the grown library — incl. TRANSFER to an unseen task
    assert result.train_usefulness.results()["solved"] == 2
    assert result.transfer.results()["solved"] == 1


def test_learn_run_resumes_from_sleep_checkpoint(tmp_path: Path) -> None:
    spec = RunSpec(config=_learn_config(), corpus=_TRAIN)
    first = execute(spec, runs_root=tmp_path)
    all_rows = list(first.trace_rows())
    assert [row["phase"] for row in all_rows] == ["wake", "sleep", "wake", "sleep"]

    # simulate a crash after iteration 0's sleep: results gone, trace truncated
    first.results_path.unlink()
    with first.trace_path.open("w", encoding="utf-8") as trace:
        for row in all_rows[:2]:
            trace.write(json.dumps(row, sort_keys=True) + "\n")

    record = execute(spec, runs_root=tmp_path)
    results = record.results()
    assert results["converged"] is True
    assert results["iterations_run"] == 2
    assert results["added"] == ["abs0"]  # replayed from the checkpoint, not re-minted twice
    assert [row["phase"] for row in record.trace_rows()] == ["wake", "sleep", "wake", "sleep"]


def test_activity_guards(tmp_path: Path) -> None:
    learn_config = _learn_config()
    search_config = learn_config.with_(learn=None)
    with pytest.raises(ValueError, match="use run_search_learn"):
        run_search(learn_config, _TRAIN, runs_root=tmp_path)
    with pytest.raises(ValueError, match="use run_search"):
        run_search_learn(search_config, _TRAIN, runs_root=tmp_path)


def test_analyze_run_reads_both_run_kinds(tmp_path: Path) -> None:
    result = run_search_learn(_learn_config(), _TRAIN, runs_root=tmp_path)

    learn_summary = analyze_run(result.learn.run_id, runs_root=tmp_path)
    trajectory = learn_summary["trajectory"]
    assert isinstance(trajectory, list)
    assert [row["phase"] for row in trajectory] == ["wake", "sleep", "wake", "sleep"]
    assert trajectory[1]["added"] == ["abs0"]

    search_summary = analyze_run(result.train_usefulness.run_id, runs_root=tmp_path)
    programs = search_summary["programs"]
    assert isinstance(programs, dict)
    assert set(programs) == {"t1", "t2"}
    # The trace stores programs as codec dicts; analyze_run must decode them to readable source,
    # not ``str()`` the raw dict (which would leak ``{'op': 'apply', ...}``).
    found = [p for progs in programs.values() for p in progs]
    assert found, "the train-usefulness run solves both tasks, so programs must be present"
    assert all("input" in p and not p.lstrip().startswith("{") for p in found)
    considered = search_summary["considered_by_task"]
    assert isinstance(considered, dict)
    assert all(count > 0 for count in considered.values())

    with pytest.raises(FileNotFoundError):
        analyze_run("nope", runs_root=tmp_path)


def _wake_rows(record_trace_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [row for row in record_trace_rows if row.get("phase") == "wake"]


def test_skip_solved_wakes_search_only_the_unsolved(tmp_path: Path) -> None:
    # Iteration 0 solves both tasks; under `skip-solved` iteration 1's wake must re-search
    # NOTHING (solutions carry), where a `full` wake re-searches everything. The wake rows carry
    # the arm label so no report can mistake this for a full-wake cost measurement.
    import dataclasses

    config = _learn_config(iterations=2)
    assert config.learn is not None
    config = config.with_(
        learn=dataclasses.replace(config.learn, wake_schedule="skip-solved", early_stop=False)
    )
    record = execute(RunSpec(config=config, corpus=_TRAIN), runs_root=tmp_path)
    wakes = _wake_rows(list(record.trace_rows()))
    assert len(wakes) == 2
    assert all(row["schedule"] == "skip-solved" for row in wakes)
    first_stats = wakes[0]["search_stats"]
    second_stats = wakes[1]["search_stats"]
    assert isinstance(first_stats, dict) and sorted(first_stats) == ["t1", "t2"]
    assert isinstance(second_stats, dict) and sorted(second_stats) == []  # nothing re-searched
    assert wakes[1]["solved"] == ["t1", "t2"]  # carried solutions still reach sleep
    assert record.results()["wake_schedule"] == "skip-solved"


def test_curriculum_wakes_search_exactly_their_group(tmp_path: Path) -> None:
    # The oracle-schedule arm: iteration i searches exactly curriculum[i] (later iterations:
    # the full corpus). The groups are explicit task ids in run identity -- the executor never
    # infers a schedule from task metadata.
    import dataclasses

    config = _learn_config(iterations=3)
    assert config.learn is not None
    config = config.with_(
        learn=dataclasses.replace(
            config.learn,
            wake_schedule="curriculum",
            curriculum=(("t1",), ("t2",)),
            early_stop=False,
        )
    )
    record = execute(RunSpec(config=config, corpus=_TRAIN), runs_root=tmp_path)
    wakes = _wake_rows(list(record.trace_rows()))
    assert len(wakes) == 3
    assert [row.get("scheduled") for row in wakes] == [["t1"], ["t2"], None]
    first, second, third = (row["search_stats"] for row in wakes)
    assert isinstance(first, dict) and sorted(first) == ["t1"]
    assert isinstance(second, dict) and sorted(second) == ["t2"]
    # Iteration 2 is past the last group -> full corpus, but both tasks are carried: no re-search.
    assert isinstance(third, dict) and sorted(third) == []
    assert wakes[2]["solved"] == ["t1", "t2"]
