from __future__ import annotations

import pytest

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.eval.scoring import score_task, score_test_input

_G = Grid.from_list


def test_score_test_input_second_attempt_counts() -> None:
    target = _G([[1]])
    assert score_test_input([_G([[0]]), _G([[1]])], target) is True


def test_score_test_input_third_attempt_ignored() -> None:
    target = _G([[1]])
    # Correct answer is only the 3rd candidate — outside the 2-attempt window.
    assert score_test_input([_G([[0]]), _G([[0]]), _G([[1]])], target) is False


def _task() -> Task:
    return Task.from_dict(
        "t",
        {
            "train": [{"input": [[1]], "output": [[1]]}],
            "test": [
                {"input": [[2]], "output": [[2]]},
                {"input": [[3]], "output": [[3]]},
            ],
        },
    )


def test_task_solved_requires_all_test_inputs() -> None:
    task = _task()
    solved, per_test = score_task(task, [[_G([[2]])], [_G([[9]])]])
    assert per_test == (True, False)
    assert solved is False

    solved, per_test = score_task(task, [[_G([[2]])], [_G([[3]])]])
    assert per_test == (True, True)
    assert solved is True


def test_score_task_rejects_missing_outputs() -> None:
    task = Task.from_dict("t", {"train": [], "test": [{"input": [[1]]}]})
    with pytest.raises(ValueError):
        score_task(task, [[_G([[1]])]])
