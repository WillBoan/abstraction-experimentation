"""Deterministic synthetic testbeds: generate tasks from known solutions + a manifest.

Corpus *generation* is its own concern (EXECUTION.md) — seeded, deterministic, rare, and
committed — deliberately disentangled from corpus *consumption*: a study that regenerated
corpora inline would silently mint new run identities whenever generation logic changed,
killing cache reuse. Studies take corpora; this package makes them.

A testbed is a controlled environment for the learning loop: tasks whose ground-truth
solutions we *choose*, so we control which structure recurs (what there is to abstract),
how much it recurs, and the held-out split for transfer. Solutions are given as plain
reference functions (e.g. ``np.rot90``) — independent of the DSL — so the task defines the
*operation*, and the system must discover a program for it from the starting primitives.

Generated tasks are written as ARC-format JSON under ``testbeds/<name>/tasks/`` (so they
load exactly like a real dataset — ``core.dataset.load_testbed``) plus a ``manifest.json``
recording each task's ground-truth label, its split, and a content hash — the recipe that
makes a testbed inspectable, reproducible, and traceable from a run. The manifest hash uses
``core.hashing`` (the one hashing discipline); it is provenance only — run identity always
comes from ``Corpus.content_hash``.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from arc_lab.core.grid import Grid
from arc_lab.core.hashing import content_id

#: A ground-truth solution: a reference input->output grid function (e.g. rot90).
Solution: TypeAlias = Callable[[Grid], Grid]


@dataclass(frozen=True, slots=True)
class GeneratedTask:
    task_id: str
    label: str  # the ground-truth solution's name (an observable, not shown to the loop)
    split: str  # "train" | "heldout"
    spec: Mapping[str, object]  # the ARC-format {train, test} dict


def make_task(
    task_id: str,
    *,
    label: str,
    split: str,
    solution: Solution,
    train_inputs: Sequence[Grid],
    test_inputs: Sequence[Grid],
) -> GeneratedTask:
    """Build one task by applying ``solution`` to the given input grids."""

    def pair(grid: Grid) -> dict[str, object]:
        return {"input": grid.array.tolist(), "output": solution(grid).array.tolist()}

    spec = {
        "train": [pair(g) for g in train_inputs],
        "test": [pair(g) for g in test_inputs],
    }
    return GeneratedTask(task_id=task_id, label=label, split=split, spec=spec)


def write_testbed(
    name: str, tasks: Sequence[GeneratedTask], *, out_root: Path, note: str = ""
) -> Path:
    """Write ``tasks`` as an ARC-format testbed under ``out_root/<name>/`` (+ a manifest)."""
    root = out_root / name
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        (tasks_dir / f"{task.task_id}.json").write_text(json.dumps(task.spec), encoding="utf-8")

    manifest = {
        "name": name,
        "note": note,
        "content_hash": content_id({"name": name, "tasks": [dict(t.spec) for t in tasks]}),
        "tasks": [{"task_id": t.task_id, "label": t.label, "split": t.split} for t in tasks],
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return root


__all__ = ["GeneratedTask", "Solution", "make_task", "write_testbed"]
