"""Control primitives over the generic enumerator.

These lock the first-order polymorphic step: ``eq`` and ``if`` should not merely parse, but be
searchable as ordinary primitives over the existing floor. The target task needs a whole-grid branch
whose condition is an integer perceiver comparison, so the solver must couple a shared type variable
across both ``if`` branches and ground ``eq`` at ``INT``.
"""

from __future__ import annotations

import numpy as np

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search.enumerate import Enumerate
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.primitives.build import HEIGHT, WIDTH
from arc_lab.solvers.dsl.substrate.primitives.control import CONTROL_PRIMITIVES
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY


def _branch_task() -> Task:
    square = [[1, 2], [3, 4]]
    rect = [[1, 2, 3], [4, 5, 6]]
    test = [[7, 8], [9, 0]]
    return Task.from_dict(
        "branch-on-shape",
        {
            "train": [
                {"input": rect, "output": np.rot90(np.array(rect), 1).tolist()},
                {"input": square, "output": np.array(square).T.tolist()},
            ],
            "test": [{"input": test, "output": np.array(test).T.tolist()}],
        },
    )


def _control_library() -> Library:
    return Library(
        name="control-grid",
        primitives=(
            WIDTH,
            HEIGHT,
            D4_LIBRARY.get("rot90"),
            D4_LIBRARY.get("transpose"),
            *CONTROL_PRIMITIVES,
        ),
    )


def test_enumerate_searches_polymorphic_if_over_grid_branches() -> None:
    task = _branch_task()
    result = Enumerate(max_depth=3).find(task, _control_library())
    assert len(result.programs) == 1
    program = str(result.programs[0])
    assert "if(" in program and "eq(" in program
    ex = task.test[0]
    assert result.programs[0].evaluate_grid(ex.input, _control_library()) == ex.output
