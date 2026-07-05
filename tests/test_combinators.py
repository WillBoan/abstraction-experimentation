"""Tests for the overlay and tile combinators, their search strategies, and the
symmetry solver that composes them."""

from __future__ import annotations

import pytest

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.eval.scoring import score_task
from arc_lab.solvers.dsl.search import CompositeSearch, OverlaySearch, SingleApply, TileSearch
from arc_lab.solvers.dsl.solver import SYMMETRY_LIBRARY, SymmetrySearchSolver
from arc_lab.solvers.dsl.substrate import (
    Apply,
    Const,
    Input,
    ValueType,
    evaluate,
    evaluate_grid,
    program_from_dict,
    program_to_dict,
)

_G = Grid.from_list


# -- Const nodes and typed values --------------------------------------


def test_const_evaluates_to_its_value() -> None:
    assert evaluate(Const(7, ValueType.COLOR), _G([[0]]), SYMMETRY_LIBRARY) == 7


def test_evaluate_grid_rejects_non_grid() -> None:
    with pytest.raises(TypeError):
        evaluate_grid(Const(3, ValueType.INT), _G([[0]]), SYMMETRY_LIBRARY)


def test_program_roundtrip_with_const() -> None:
    prog: object = Apply("overlay", (Const(0, ValueType.COLOR), Apply("identity", (Input(),))))
    assert program_from_dict(program_to_dict(prog)) == prog  # type: ignore[arg-type]


# -- combinator primitives directly ------------------------------------


def test_overlay_repairs_masked_symmetry() -> None:
    # A rot180-symmetric grid with cell [0,0] occluded by 0; overlaying the input
    # with its rot180 image fills the hole from the symmetric partner.
    occluded = _G([[0, 2, 3], [4, 5, 4], [3, 2, 1]])
    prog = Apply(
        "overlay",
        (Const(0, ValueType.COLOR), Apply("identity", (Input(),)), Apply("rot180", (Input(),))),
    )
    assert evaluate_grid(prog, occluded, SYMMETRY_LIBRARY) == _G([[1, 2, 3], [4, 5, 4], [3, 2, 1]])


def test_tile_builds_vertical_mirror_mosaic() -> None:
    prog = Apply(
        "tile",
        (
            Const(2, ValueType.INT),
            Const(1, ValueType.INT),
            Apply("identity", (Input(),)),
            Apply("flip_v", (Input(),)),
        ),
    )
    out = evaluate_grid(prog, _G([[1, 2], [3, 4]]), SYMMETRY_LIBRARY)
    assert out == _G([[1, 2], [3, 4], [3, 4], [1, 2]])


# -- search strategies --------------------------------------------------


def _overlay_task() -> Task:
    full = [[1, 2, 3], [4, 5, 4], [3, 2, 1]]  # rot180-symmetric
    return Task.from_dict(
        "sym",
        {
            "train": [
                {"input": [[0, 2, 3], [4, 5, 4], [3, 2, 1]], "output": full},
                {"input": [[1, 2, 0], [4, 5, 4], [3, 2, 1]], "output": full},
            ],
            "test": [{"input": [[1, 2, 3], [0, 5, 4], [3, 2, 1]], "output": full}],
        },
    )


def _tile_task() -> Task:
    def mosaic(g: list[list[int]]) -> list[list[int]]:
        return g + g[::-1]  # 2x1 vertical mirror

    return Task.from_dict(
        "tile",
        {
            "train": [
                {"input": [[1, 2], [3, 4]], "output": mosaic([[1, 2], [3, 4]])},
                {"input": [[5, 6], [7, 8]], "output": mosaic([[5, 6], [7, 8]])},
            ],
            "test": [{"input": [[9, 0], [1, 2]], "output": mosaic([[9, 0], [1, 2]])}],
        },
    )


def test_overlay_search_finds_symmetry_repair() -> None:
    found = OverlaySearch().find(_overlay_task(), SYMMETRY_LIBRARY)
    assert len(found) == 1
    assert isinstance(found[0], Apply) and found[0].primitive == "overlay"


def test_tile_search_finds_mosaic() -> None:
    found = TileSearch().find(_tile_task(), SYMMETRY_LIBRARY)
    assert len(found) == 1
    assert isinstance(found[0], Apply) and found[0].primitive == "tile"


def test_overlay_search_returns_nothing_on_geometry_task() -> None:
    flip = Task.from_dict(
        "flip",
        {
            "train": [{"input": [[1, 2]], "output": [[2, 1]]}],
            "test": [{"input": [[3, 4]], "output": [[4, 3]]}],
        },
    )
    assert OverlaySearch().find(flip, SYMMETRY_LIBRARY) == []


def test_composite_search_dedups_and_concatenates() -> None:
    # rot90 is the *only* transform mapping this 2x2 input to its output, so the
    # duplicated strategy must yield exactly one deduplicated program.
    task = Task.from_dict(
        "rot",
        {
            "train": [{"input": [[1, 2], [3, 4]], "output": [[2, 4], [1, 3]]}],
            "test": [{"input": [[5, 6], [7, 8]], "output": [[6, 8], [5, 7]]}],
        },
    )
    combined = CompositeSearch([SingleApply(), SingleApply()]).find(task, SYMMETRY_LIBRARY)
    assert combined == [Apply("rot90", (Input(),))]


# -- the composed solver ------------------------------------------------


@pytest.mark.parametrize("task_factory", [_overlay_task, _tile_task])
def test_symmetry_solver_solves_combinator_tasks(task_factory: object) -> None:
    task = task_factory()  # type: ignore[operator]
    solved, _ = score_task(task, SymmetrySearchSolver().predict(task))
    assert solved is True


def test_symmetry_solver_still_solves_single_transforms() -> None:
    flip = Task.from_dict(
        "flip",
        {
            "train": [{"input": [[1, 2, 3]], "output": [[3, 2, 1]]}],
            "test": [{"input": [[4, 5, 6]], "output": [[6, 5, 4]]}],
        },
    )
    solved, _ = score_task(flip, SymmetrySearchSolver().predict(flip))
    assert solved is True
