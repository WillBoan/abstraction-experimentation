"""Annotation model: round-trips and the core-cleanliness invariant."""

from __future__ import annotations

from arc_lab.core.annotation import (
    AnnotatedTask,
    Real,
    Split,
    Synthetic,
    TaskMeta,
    provenance_from_dict,
)
from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task


def _task(task_id: str = "t") -> Task:
    grid = Grid.from_list([[1, 2], [3, 4]])
    return Task(task_id=task_id, train=(Example(grid, grid),), test=(Example(grid, grid),))


def test_provenance_round_trip() -> None:
    for prov in (Real(dataset="arc1-train"), Synthetic(generator="e1-rot90")):
        assert provenance_from_dict(prov.to_dict()) == prov


def test_task_meta_round_trip_full() -> None:
    meta = TaskMeta(provenance=Synthetic("e1-rot90"), split=Split.HELDOUT, label="rot90")
    assert TaskMeta.from_dict(meta.to_dict()) == meta


def test_task_meta_round_trip_minimal() -> None:
    meta = TaskMeta(provenance=Real("arc1-eval"))
    restored = TaskMeta.from_dict(meta.to_dict())
    assert restored == meta
    assert restored.split is None and restored.label is None


def test_annotated_task_holds_pure_task() -> None:
    task = _task()
    annotated = AnnotatedTask(task=task, meta=TaskMeta(provenance=Real("arc1-train")))
    # The solver-facing accessor is the pure Task — meta never reaches it.
    assert annotated.task is task
    assert not hasattr(annotated.task, "meta")


def test_split_values() -> None:
    assert Split("train") is Split.TRAIN
    assert Split("heldout") is Split.HELDOUT
