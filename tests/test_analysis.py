"""Tests for the analysis layer: search stats, compression, and the run artifact."""

from __future__ import annotations

import json
from pathlib import Path

from arc_lab.core.annotation import AnnotatedTask
from arc_lab.core.dataset import Dataset
from arc_lab.core.task import Task
from arc_lab.solvers.dsl.analysis import (
    CompressionMetric,
    RunSummary,
    TwoPartMDL,
    analyze,
    compression_ratio,
)
from arc_lab.solvers.dsl.analysis.artifact import SUMMARY_FILE, TRACE_FILE
from arc_lab.solvers.dsl.analysis.compression import SolvedTask
from arc_lab.solvers.dsl.config import PRESETS
from arc_lab.solvers.dsl.search import SearchStats
from arc_lab.solvers.dsl.solver import ProgramSearchSolver
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.solvers.dsl.substrate.program import Apply, Input, Param
from arc_lab.solvers.dsl.substrate.types import GRID


def _flip_task(task_id: str = "flip") -> Task:
    # 2D so flip_h is the *unique* D4 transform (on a single row, rot180 would tie).
    return Task.from_dict(
        task_id,
        {
            "train": [{"input": [[1, 2], [3, 4]], "output": [[2, 1], [4, 3]]}],
            "test": [{"input": [[5, 6], [7, 8]], "output": [[6, 5], [8, 7]]}],
        },
    )


def _rot180_task(task_id: str = "rot") -> Task:
    return Task.from_dict(
        task_id,
        {
            "train": [{"input": [[1, 2], [3, 4]], "output": [[4, 3], [2, 1]]}],
            "test": [{"input": [[5, 6], [7, 8]], "output": [[8, 7], [6, 5]]}],
        },
    )


def _dataset(*tasks: Task) -> Dataset:
    return Dataset.of("tiny", tasks)


# -- SearchStats (the standardised, centralised summary) ----------------


def test_search_stats_summary_is_derived_from_counters() -> None:
    stats = SearchStats(strategy="Enumerate", considered=9, returned=1, extra={"deduped": 4})
    assert stats.solved is True
    assert stats.summary() == "Enumerate: considered=9 returned=1 deduped=4 solved=True"


def test_search_stats_solved_false_when_empty() -> None:
    assert SearchStats(strategy="X", considered=3, returned=0).solved is False


# -- Library / Primitive serialisation ----------------------------------


def test_library_to_dict_captures_signature_identity() -> None:
    data = D4_LIBRARY.to_dict()
    assert data["name"] == D4_LIBRARY.name
    assert data["version"] == D4_LIBRARY.version
    prims = data["primitives"]
    assert isinstance(prims, list) and len(prims) == len(D4_LIBRARY.primitives)
    flip = next(p for p in prims if p["name"] == "flip_h")
    assert flip == {
        "name": "flip_h",
        "param_types": ["grid"],
        "return_type": "grid",
        "variadic_param": None,
    }


# -- CompressionMetric (two-part MDL) -----------------------------------


def test_compression_two_part_description_length() -> None:
    task = _flip_task()
    program = Apply("flip_h", (Input(),))  # size 2
    metric = CompressionMetric()  # bits_per_primitive=1.0, ProgramSize
    dl = metric.describe([SolvedTask(AnnotatedTask(task), program)], D4_LIBRARY)
    assert dl.library_bits == float(len(D4_LIBRARY.primitives))  # 8 primitives
    assert dl.program_bits == 2.0
    assert dl.total == dl.library_bits + dl.program_bits


def test_compression_ratio_direction() -> None:
    # A more compact (smaller) description of the same corpus scores > 1.
    assert compression_ratio(20.0, 10.0) == 2.0
    assert compression_ratio(10.0, 0.0) == float("inf")


def test_two_part_mdl_charges_learned_template_size() -> None:
    # A learned abstraction pays its definition size on top of the flat name cost;
    # base primitives (no template) do not, so the two metrics agree until one is learned.
    template = Apply("transpose", (Apply("flip_h", (Param(0, GRID),)),))  # size 3
    learned = make_abstraction("learned_rot90", template, D4_LIBRARY)
    library = D4_LIBRARY.extended(name="d4+learned", extra=(learned,))
    assert CompressionMetric().library_bits(D4_LIBRARY) == TwoPartMDL().library_bits(D4_LIBRARY)
    assert TwoPartMDL().library_bits(library) == CompressionMetric().library_bits(library) + 3.0


# -- The run artifact: end-to-end, caching, resume ----------------------


def test_analyze_writes_artifact_and_solves(tmp_path: Path) -> None:
    ds = _dataset(_flip_task(), _rot180_task())
    summary, run_dir = analyze(
        ProgramSearchSolver.from_config(PRESETS["dsl"]), ds, out_dir=tmp_path
    )

    assert summary.total == 2
    assert summary.solved == 2
    assert summary.search_solved == 2
    assert summary.description_length > 0
    assert (run_dir / SUMMARY_FILE).exists()
    assert (run_dir / "library.json").exists()
    assert (run_dir / TRACE_FILE).exists()

    # The summary round-trips through its serialised form.
    reloaded = RunSummary.from_dict(json.loads((run_dir / SUMMARY_FILE).read_text()))
    assert reloaded.solved == 2
    assert reloaded.coordinates.solver == "dsl"

    # Each solved task recorded the program it found.
    flip_row = next(r for r in summary.records if r.task_id == "flip")
    assert flip_row.program == "flip_h(input)"
    assert flip_row.program_size == 2


def test_analyze_is_cached_and_idempotent(tmp_path: Path) -> None:
    ds = _dataset(_flip_task())
    solver = ProgramSearchSolver.from_config(PRESETS["dsl"])
    _, run_dir = analyze(solver, ds, out_dir=tmp_path)

    # A cache hit returns without redoing work: delete the library artifact and confirm
    # a second call (summary.json present) does NOT rewrite it.
    (run_dir / "library.json").unlink()
    analyze(solver, ds, out_dir=tmp_path)
    assert not (run_dir / "library.json").exists()

    # force=True ignores the cache and recomputes everything.
    analyze(solver, ds, out_dir=tmp_path, force=True)
    assert (run_dir / "library.json").exists()


def test_analyze_resumes_from_partial_trace(tmp_path: Path) -> None:
    ds = _dataset(_flip_task(), _rot180_task())
    solver = ProgramSearchSolver.from_config(PRESETS["dsl"])
    _, run_dir = analyze(solver, ds, out_dir=tmp_path)

    # Simulate a crash after the first task: keep only the first trace line, drop summary.
    trace_path = run_dir / TRACE_FILE
    first_line = trace_path.read_text().splitlines()[0]
    trace_path.write_text(first_line + "\n")
    (run_dir / SUMMARY_FILE).unlink()

    # Re-running resumes: the second task is processed and the run completes.
    summary, _ = analyze(solver, ds, out_dir=tmp_path)
    assert summary.total == 2
    assert {r.task_id for r in summary.records} == {"flip", "rot"}
