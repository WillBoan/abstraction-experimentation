"""taskgen: generated testbeds are ARC-format, deterministic, and load via the core loader."""

from __future__ import annotations

import json
from pathlib import Path

from arc_lab.core.dataset import Corpus
from arc_lab.core.grid import Grid
from arc_lab.core.task import load_tasks
from arc_lab.taskgen import make_task, write_testbed

_A = Grid.from_list([[1, 2], [3, 4]])
_B = Grid.from_list([[5, 6], [7, 8]])
_C = Grid.from_list([[9, 0], [1, 2]])


def _rot180(grid: Grid) -> Grid:
    return Grid(grid.array[::-1, ::-1])


def _testbed(out_root: Path) -> Path:
    tasks = [
        make_task(
            "t1",
            label="rot180",
            split="train",
            solution=_rot180,
            train_inputs=[_A, _B],
            test_inputs=[_C],
        ),
        make_task(
            "t2",
            label="rot180",
            split="heldout",
            solution=_rot180,
            train_inputs=[_C],
            test_inputs=[_A],
        ),
    ]
    return write_testbed("rot180-bed", tasks, out_root=out_root, note="unit test")


def test_generated_tasks_apply_the_solution_and_load_arc_format(tmp_path: Path) -> None:
    root = _testbed(tmp_path)

    loaded = load_tasks(root / "tasks")  # the same loader real datasets use
    corpus = Corpus.of("rot180-bed", list(loaded))
    assert [task.task_id for task in corpus] == ["t1", "t2"]

    t1 = corpus.get("t1")
    assert len(t1.train) == 2 and len(t1.test) == 1
    assert t1.train[0].input == _A
    assert t1.train[0].output == _rot180(_A)
    assert t1.test[0].output == _rot180(_C)


def test_manifest_records_labels_splits_and_content_hash(tmp_path: Path) -> None:
    root = _testbed(tmp_path)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["name"] == "rot180-bed"
    assert manifest["note"] == "unit test"
    assert isinstance(manifest["content_hash"], str) and len(manifest["content_hash"]) == 16
    assert manifest["tasks"] == [
        {"task_id": "t1", "label": "rot180", "split": "train"},
        {"task_id": "t2", "label": "rot180", "split": "heldout"},
    ]


def test_generation_is_deterministic(tmp_path: Path) -> None:
    first = _testbed(tmp_path / "one")
    second = _testbed(tmp_path / "two")
    assert (first / "manifest.json").read_text() == (second / "manifest.json").read_text()
    for task_file in sorted((first / "tasks").iterdir()):
        twin = second / "tasks" / task_file.name
        assert task_file.read_text() == twin.read_text()
