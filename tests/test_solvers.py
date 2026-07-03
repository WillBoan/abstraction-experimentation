from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.eval.scoring import score_task
from arc_lab.solvers import make_solver
from arc_lab.solvers.baseline import IdentitySolver
from arc_lab.solvers.dsl import GeometricSearchSolver

_G = Grid.from_list


def test_identity_solver() -> None:
    task = Task.from_dict(
        "t",
        {
            "train": [{"input": [[1, 2]], "output": [[1, 2]]}],
            "test": [{"input": [[3, 4]], "output": [[3, 4]]}],
        },
    )
    solved, _ = score_task(task, IdentitySolver().predict(task))
    assert solved is True


def test_dsl_solver_learns_horizontal_flip() -> None:
    # Every train pair is a left-right flip; the test must be flipped too.
    task = Task.from_dict(
        "flip",
        {
            "train": [
                {"input": [[1, 2, 3]], "output": [[3, 2, 1]]},
                {"input": [[4, 5, 6]], "output": [[6, 5, 4]]},
            ],
            "test": [{"input": [[7, 8, 9]], "output": [[9, 8, 7]]}],
        },
    )
    prediction = GeometricSearchSolver().predict(task)
    solved, _ = score_task(task, prediction)
    assert solved is True


def test_dsl_solver_falls_back_to_identity() -> None:
    # No geometric transform fits; the solver must still return a valid grid.
    task = Task.from_dict(
        "nope",
        {
            "train": [{"input": [[1]], "output": [[2]]}],
            "test": [{"input": [[3]], "output": [[3]]}],
        },
    )
    prediction = GeometricSearchSolver().predict(task)
    assert prediction == [[_G([[3]])]]


def test_registry_make_solver() -> None:
    assert isinstance(make_solver("dsl"), GeometricSearchSolver)
    assert isinstance(make_solver("identity"), IdentitySolver)
