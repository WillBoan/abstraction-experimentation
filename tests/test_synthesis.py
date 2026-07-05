"""Tests for the atomic primitives and the typed enumeration engine."""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.eval.scoring import score_task
from arc_lab.solvers.dsl.search import Enumerate
from arc_lab.solvers.dsl.solver import ATOMIC_LIBRARY, SynthesisSolver
from arc_lab.solvers.dsl.substrate import Apply, Const, Input, ValueType, evaluate_grid

_G = Grid.from_list


# -- atomic primitives --------------------------------------------------


def test_map_color_recolors_one_color() -> None:
    prog = Apply("map_color", (Input(), Const(2, ValueType.COLOR), Const(5, ValueType.COLOR)))
    assert evaluate_grid(prog, _G([[1, 2], [2, 3]]), ATOMIC_LIBRARY) == _G([[1, 5], [5, 3]])


def test_scale_expands_by_factor() -> None:
    prog = Apply("scale", (Input(), Const(2, ValueType.INT)))
    out = evaluate_grid(prog, _G([[1, 2]]), ATOMIC_LIBRARY)
    assert out == _G([[1, 1, 2, 2], [1, 1, 2, 2]])


def test_scale_out_of_range_is_noop() -> None:
    # A factor that would exceed the max ARC side returns the grid unchanged.
    prog = Apply("scale", (Input(), Const(9, ValueType.INT)))
    big = _G([[c % 10 for c in range(5)] for _ in range(5)])
    assert evaluate_grid(prog, big, ATOMIC_LIBRARY) == big


# -- enumeration: single primitives -------------------------------------


def _recolor_task() -> Task:
    return Task.from_dict(
        "recolor",
        {
            "train": [
                {"input": [[1, 2], [3, 1]], "output": [[4, 2], [3, 4]]},
                {"input": [[1, 1], [2, 1]], "output": [[4, 4], [2, 4]]},
            ],
            "test": [{"input": [[3, 1], [1, 2]], "output": [[3, 4], [4, 2]]}],
        },
    )


def _scale_task() -> Task:
    return Task.from_dict(
        "scale",
        {
            "train": [
                {"input": [[1, 2]], "output": [[1, 1, 2, 2], [1, 1, 2, 2]]},
                {"input": [[3, 4]], "output": [[3, 3, 4, 4], [3, 3, 4, 4]]},
            ],
            "test": [{"input": [[5, 6]], "output": [[5, 5, 6, 6], [5, 5, 6, 6]]}],
        },
    )


def test_enumerate_solves_recolor() -> None:
    found = Enumerate(max_depth=1).find(_recolor_task(), ATOMIC_LIBRARY)
    assert len(found) == 1


def test_enumerate_solves_scale() -> None:
    found = Enumerate(max_depth=1).find(_scale_task(), ATOMIC_LIBRARY)
    assert len(found) == 1


def test_enumerate_returns_nothing_when_unsolvable() -> None:
    # No composition of geometry/color/scale maps this input to this output.
    task = Task.from_dict(
        "hard",
        {
            "train": [{"input": [[1, 2], [3, 4]], "output": [[9, 0], [0, 9]]}],
            "test": [{"input": [[5, 6], [7, 8]], "output": [[9, 0], [0, 9]]}],
        },
    )
    assert Enumerate(max_depth=2).find(task, ATOMIC_LIBRARY) == []


# -- enumeration: composition (depth matters) ---------------------------


def _composition_task() -> Task:
    # Output = map_color(rot180(input), 1 -> 4): solvable only by a depth-2 program.
    return Task.from_dict(
        "compose",
        {
            "train": [
                {"input": [[1, 2], [3, 1]], "output": [[4, 3], [2, 4]]},
                {"input": [[2, 1], [1, 3]], "output": [[3, 4], [4, 2]]},
            ],
            "test": [{"input": [[1, 1], [2, 3]], "output": [[3, 2], [4, 4]]}],
        },
    )


def test_depth_one_cannot_solve_composition() -> None:
    task = _composition_task()
    solved, _ = score_task(task, SynthesisSolver(max_depth=1).predict(task))
    assert solved is False


def test_depth_two_solves_composition() -> None:
    task = _composition_task()
    solved, _ = score_task(task, SynthesisSolver(max_depth=2).predict(task))
    assert solved is True


def test_synthesis_solver_still_solves_geometry() -> None:
    flip = Task.from_dict(
        "flip",
        {
            "train": [{"input": [[1, 2, 3]], "output": [[3, 2, 1]]}],
            "test": [{"input": [[4, 5, 6]], "output": [[6, 5, 4]]}],
        },
    )
    solved, _ = score_task(flip, SynthesisSolver(max_depth=1).predict(flip))
    assert solved is True
