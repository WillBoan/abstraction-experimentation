from __future__ import annotations

import json
from pathlib import Path

import pytest

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task, load_tasks

_TASK = {
    "train": [
        {"input": [[1, 0]], "output": [[0, 1]]},
        {"input": [[2, 0]], "output": [[0, 2]]},
    ],
    "test": [{"input": [[3, 0]], "output": [[0, 3]]}],
}


def test_from_dict() -> None:
    task = Task.from_dict("demo", _TASK)
    assert task.task_id == "demo"
    assert len(task.train) == 2
    assert len(task.test) == 1
    assert task.train[0].input == Grid.from_list([[1, 0]])
    assert task.train[0].output == Grid.from_list([[0, 1]])


def test_test_outputs_present() -> None:
    task = Task.from_dict("demo", _TASK)
    outs = task.test_outputs
    assert outs is not None
    assert outs[0] == Grid.from_list([[0, 3]])


def test_test_outputs_missing() -> None:
    data = {"train": _TASK["train"], "test": [{"input": [[3, 0]]}]}
    task = Task.from_dict("demo", data)
    assert task.test[0].output is None
    assert task.test_outputs is None


def test_from_json_file(tmp_path: Path) -> None:
    p = tmp_path / "abc123.json"
    p.write_text(json.dumps(_TASK), encoding="utf-8")
    task = Task.from_json_file(p)
    assert task.task_id == "abc123"


def test_load_tasks_empty_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_tasks(tmp_path)
