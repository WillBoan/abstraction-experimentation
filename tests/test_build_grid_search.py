"""BuildGridSearch: finding size-general build_grid programs by open-term body enumeration.

These lock the search's core claim (it re-derives D4 members as coordinate lambdas, generalising
to unseen shapes) and the measured **difficulty ladder** — transpose falls out with zero coordinate
arithmetic; rot90 needs the depth-2 reflection `width-1-i`.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import numpy.typing as npt

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search import BuildGridSearch
from arc_lab.solvers.dsl.substrate.primitives.build import BUILD_LIBRARY
from arc_lab.solvers.dsl.substrate.program import Program

_Ref = Callable[[npt.NDArray[np.int_]], npt.NDArray[np.int_]]

# Varied shapes (square + both non-square) so only a *size-general* coordinate program can fit.
_TRAIN_SHAPES = [[[1, 2], [3, 4]], [[1, 2, 3], [4, 5, 6]], [[1, 2], [3, 4], [5, 6]]]
_TEST_SHAPE = [[7, 8, 9], [1, 2, 3]]


def _task(ref: _Ref) -> Task:
    def pair(rows: list[list[int]]) -> dict[str, object]:
        return {"input": rows, "output": ref(np.array(rows)).tolist()}

    return Task.from_dict(
        "t", {"train": [pair(r) for r in _TRAIN_SHAPES], "test": [pair(_TEST_SHAPE)]}
    )


def _generalises(task: Task, program: Program) -> bool:
    # The held-out test input is a shape unseen in training — size-generality, end to end.
    ex = task.test[0]
    return bool(program.evaluate_grid(ex.input, BUILD_LIBRARY) == ex.output)


def test_finds_rot90() -> None:
    task = _task(lambda a: np.rot90(a, 1))
    found = BuildGridSearch().find(task, BUILD_LIBRARY).programs
    assert len(found) == 1
    assert str(found[0]).startswith("build_grid(")
    assert _generalises(task, found[0])


def test_finds_flip_h() -> None:
    task = _task(np.fliplr)
    found = BuildGridSearch().find(task, BUILD_LIBRARY).programs
    assert len(found) == 1
    assert _generalises(task, found[0])


def test_finds_transpose() -> None:
    task = _task(lambda a: a.T)
    found = BuildGridSearch().find(task, BUILD_LIBRARY).programs
    assert len(found) == 1
    assert _generalises(task, found[0])


def test_difficulty_ladder_depth() -> None:
    transpose, rot90 = _task(lambda a: a.T), _task(lambda a: np.rot90(a, 1))
    # transpose's coords are the bare bound vars ($0, $1) -> reachable with no arithmetic.
    assert BuildGridSearch(max_coord_depth=0).find(transpose, BUILD_LIBRARY).programs
    # rot90's column is `width-1-i`, a depth-2 sub-expression: out of reach at depth 0, found at 2.
    assert not BuildGridSearch(max_coord_depth=0).find(rot90, BUILD_LIBRARY).programs
    assert BuildGridSearch(max_coord_depth=2).find(rot90, BUILD_LIBRARY).programs
