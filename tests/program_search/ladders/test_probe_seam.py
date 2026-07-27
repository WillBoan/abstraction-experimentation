"""The probe/execution seam: a probe cell IS a recorded run.

The probe's claim is that it puts a rung to "the real engine" before a ladder run exists. That was
only true by coincidence while it spelled out ``engine.run(...)`` itself -- two code paths whose
agreement was checked by hand once (2026-07-22) and never again. Since 2026-07-26 a probe cell goes
through ``execute()`` like anything else: cached, crash-safe, resumable, recorded.

That introduces one real risk, which is what these tests exist for. The probe no longer reads the
engine's return value; it reads the trace and rebuilds it (``execute.search_result_from_row``). A
field the writer emits and the reader forgets would NOT raise -- it would quietly become a default,
and a probe verdict would come back plausible and wrong. So the round trip is pinned FIELD BY
FIELD against the same search run directly through the engine.

Cheap because ``al21-dag-siblings`` is the batch's deliberately-tiny DAG instrument.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from arc_lab.core.dataset import Corpus
from arc_lab.program_search.execution.execute import (
    execute,
    search_once,
    search_result_from_row,
)
from arc_lab.program_search.execution.model.run_spec import RunSpec
from arc_lab.program_search.ladders.probe import PROBE_CORPUS_PREFIX, probe_rung
from arc_lab.program_search.ladders.registry import make_ladder
from arc_lab.program_search.search.search_result import SearchStats

LADDER = "al21-dag-siblings"


def test_the_trace_round_trip_is_lossless(tmp_path: Path) -> None:
    """THE hazard of recording the probe: it now reads a rebuilt result, not the engine's own.

    Every ``SearchStats`` field is compared against the same search driven straight through the
    engine. A field the writer emits and the reader drops would otherwise degrade silently -- the
    rebuilt stats would carry a default, and the probe would report a confident wrong verdict.
    """
    spec = make_ladder(LADDER)
    task = next(e.task for e in spec.train_corpus.entries if e.task.task_id.startswith("mirror_h-"))
    budget = dataclasses.replace(
        spec.reference_config.budget, depth_limit=spec.lint().depth_schedule[0]
    )
    config = spec.reference_config.with_(library=spec.oracle_library(0), budget=budget, learn=None)

    direct = search_once(task, config, config.library)
    record = execute(
        RunSpec(config=config, corpus=Corpus.of(f"{LADDER}:roundtrip", [task])),
        runs_root=tmp_path,
    )
    row = next(r for r in record.trace_rows() if r.get("task_id") == task.task_id)
    rebuilt = search_result_from_row(row)
    assert rebuilt is not None

    assert rebuilt.ranked_programs == direct.ranked_programs
    for field in dataclasses.fields(SearchStats):
        expected = getattr(direct.stats, field.name)
        actual = getattr(rebuilt.stats, field.name)
        if field.name == "generations":  # JSON round-trips the funnel rows as plain dicts
            assert [dict(g) for g in actual] == [dict(g) for g in expected], field.name
        elif field.name in ("outcomes", "by_primitive"):
            assert dict(actual) == dict(expected), field.name
        else:
            assert actual == expected, field.name
    # ...and the derived property everything downstream reads, which a 0 default would break.
    assert rebuilt.stats.solved == direct.stats.solved


def test_a_probe_cell_is_a_cached_recorded_run(tmp_path: Path) -> None:
    """What recording bought: a re-probe of an unchanged rung is a cache hit, not a re-enumeration,
    and the cell is inspectable afterwards under its own namespace."""
    spec = make_ladder(LADDER)
    first = probe_rung(spec, 1, runs_root=tmp_path)
    dirs = {p for p in tmp_path.glob("*/*") if p.is_dir()}
    assert dirs, "a probe cell must leave a recorded run"

    names = [
        json.loads((d / "runspec.json").read_text(encoding="utf-8"))["corpus_name"] for d in dirs
    ]
    assert all(n.startswith(PROBE_CORPUS_PREFIX) for n in names), names

    second = probe_rung(spec, 1, runs_root=tmp_path)  # identical cells -> served from cache
    assert {p for p in tmp_path.glob("*/*") if p.is_dir()} == dirs
    assert second.wake[0].considered == first.wake[0].considered
    assert second.wake[0].verdict == first.wake[0].verdict


def test_the_probe_and_a_recorded_run_report_the_same_funnel(tmp_path: Path) -> None:
    spec = make_ladder(LADDER)
    probe = probe_rung(spec, 1, runs_root=tmp_path)
    cell = probe.wake[0]

    # The same cell as a recorded run: rung 1's search is over L_0, at level 0's derived budget.
    task = next(e.task for e in spec.train_corpus.entries if e.task.task_id == cell.task_id)
    budget = dataclasses.replace(
        spec.reference_config.budget, depth_limit=spec.lint().depth_schedule[0]
    )
    config = spec.reference_config.with_(library=spec.oracle_library(0), budget=budget, learn=None)
    record = execute(
        RunSpec(config=config, corpus=Corpus.of(f"{LADDER}:seam", [task])), runs_root=tmp_path
    )

    row = next(r for r in record.trace_rows() if r.get("task_id") == cell.task_id)
    stats = row["search_stats"]
    assert isinstance(stats, dict)
    total = stats["total"]
    assert isinstance(total, dict)

    # The funnel is the seam: same considered count, same solve round. A drift in either means the
    # probe is measuring a different search than the one the ladder will actually run.
    assert total["considered"] == cell.considered
    assert stats["solved_at_generation"] == cell.solve_generation


def test_probe_verdicts_are_a_function_of_the_search_alone(tmp_path: Path) -> None:
    """Every probe verdict must depend on the SEARCH only, never on the test examples.

    Worth pinning precisely because recording weakened the structural argument. The probe used to
    sit below ``_run_task`` and so could not see a test grid at all; now it goes through
    ``execute()``, which predicts and scores like any run. That is sound -- the probe reads
    ``search_stats`` and the retained programs, and the scorer touches neither -- but it is now a
    property of what the probe READS rather than of what it can reach, so it gets a test.

    A task whose test outputs are replaced with garbage must probe identically. (It genuinely
    re-searches: the corpus content hash changes, so the poisoned cell is a different ``run_id``
    and cannot be served from the clean one's cache.)
    """
    spec = make_ladder(LADDER)
    baseline = probe_rung(spec, 1, runs_root=tmp_path)

    from arc_lab.core.grid import Grid

    poisoned = []
    for entry in spec.train_corpus.entries:
        task = entry.task
        tests = tuple(
            dataclasses.replace(example, output=Grid.from_list([[9]])) for example in task.test
        )
        poisoned.append(dataclasses.replace(entry, task=dataclasses.replace(task, test=tests)))
    corrupted = dataclasses.replace(
        spec, train_corpus=Corpus.of(spec.train_corpus.name, [e.task for e in poisoned])
    )

    poisoned_probe = probe_rung(corrupted, 1, runs_root=tmp_path)
    assert poisoned_probe.wake[0].considered == baseline.wake[0].considered
    assert poisoned_probe.wake[0].verdict == baseline.wake[0].verdict
