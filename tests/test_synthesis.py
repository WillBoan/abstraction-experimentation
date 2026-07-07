"""Tests for the atomic primitives and the typed enumeration engine."""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.eval.scoring import score_task
from arc_lab.solvers.dsl.search import BeamSearch, Enumerate, ProgramSize
from arc_lab.solvers.dsl.solver import ATOMIC_LIBRARY, SynthesisSolver
from arc_lab.solvers.dsl.substrate import Apply, Const, Input, ValueType
from arc_lab.solvers.dsl.substrate.library import Library, Primitive
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY

_G = Grid.from_list


# -- atomic primitives --------------------------------------------------


def test_map_color_recolors_one_color() -> None:
    prog = Apply("map_color", (Input(), Const(2, ValueType.COLOR), Const(5, ValueType.COLOR)))
    assert prog.evaluate_grid(_G([[1, 2], [2, 3]]), ATOMIC_LIBRARY) == _G([[1, 5], [5, 3]])


def test_scale_expands_by_factor() -> None:
    prog = Apply("scale", (Input(), Const(2, ValueType.INT)))
    out = prog.evaluate_grid(_G([[1, 2]]), ATOMIC_LIBRARY)
    assert out == _G([[1, 1, 2, 2], [1, 1, 2, 2]])


def test_scale_out_of_range_is_noop() -> None:
    # A factor that would exceed the max ARC side returns the grid unchanged.
    prog = Apply("scale", (Input(), Const(9, ValueType.INT)))
    big = _G([[c % 10 for c in range(5)] for _ in range(5)])
    assert prog.evaluate_grid(big, ATOMIC_LIBRARY) == big


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
    found = Enumerate(max_depth=1).find(_recolor_task(), ATOMIC_LIBRARY).programs
    assert len(found) == 1


def test_enumerate_solves_scale() -> None:
    found = Enumerate(max_depth=1).find(_scale_task(), ATOMIC_LIBRARY).programs
    assert len(found) == 1


def test_enumerate_keeps_the_smallest_program_per_behavior() -> None:
    # Within one round a larger equivalent can be formed before a smaller one, so keep-smallest
    # must return the minimal witness. `flip_pair` (binary: flips its first arg, ignores the
    # second) is ordered BEFORE `flip_h`, so under first-considered dedup the size-3
    # `flip_pair(input, input)` would be stored; keep-smallest replaces it with `flip_h(input)`.
    flip_impl = D4_LIBRARY.get("flip_h").impl
    flip_pair = Primitive(
        name="flip_pair",
        param_types=(ValueType.GRID, ValueType.GRID),
        return_type=ValueType.GRID,
        impl=lambda a, b: flip_impl(a),
    )
    library = Library(name="ks", primitives=(flip_pair, D4_LIBRARY.get("flip_h")))
    rows = [[1, 2], [3, 4]]
    out = Apply("flip_h", (Input(),)).evaluate_grid(Grid.from_list(rows), library)
    task = Task.from_dict(
        "ks", {"train": [{"input": rows, "output": out.array.tolist()}], "test": [{"input": rows}]}
    )

    found = Enumerate(max_depth=1).find(task, library).programs
    assert found == (Apply("flip_h", (Input(),)),)  # size 2, not flip_pair(input, input) size 3


def test_enumerate_returns_nothing_when_unsolvable() -> None:
    # No composition of geometry/color/scale maps this input to this output.
    task = Task.from_dict(
        "hard",
        {
            "train": [{"input": [[1, 2], [3, 4]], "output": [[9, 0], [0, 9]]}],
            "test": [{"input": [[5, 6], [7, 8]], "output": [[9, 0], [0, 9]]}],
        },
    )
    assert Enumerate(max_depth=2).find(task, ATOMIC_LIBRARY).programs == ()


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


# -- cost-guided beam (the F1 frontier policy) --------------------------


def test_beam_search_solves_like_enumerate() -> None:
    # A wide-enough beam is near-lossless: it finds what plain enumeration finds.
    found = (
        BeamSearch(cost=ProgramSize(), beam_width=16, max_depth=1)
        .find(_recolor_task(), ATOMIC_LIBRARY)
        .programs
    )
    assert len(found) == 1


def test_beam_width_bounds_and_cost_ranks_the_frontier() -> None:
    # The depth-2 solution needs `rot180(input)` as its intermediate grid.
    task = _composition_task()
    # beam_width=1 keeps only the single cheapest grid (`input`) as the round-2 frontier, which
    # cannot form `map_color(rot180(input), ...)`: the cap is real, so the task goes unsolved.
    narrow = BeamSearch(cost=ProgramSize(), beam_width=1, max_depth=2).find(task, ATOMIC_LIBRARY)
    assert narrow.programs == ()
    # A wider beam keeps `rot180(input)` among the cheapest grids by cost, so it solves — and
    # still considers fewer programs than unbounded enumeration.
    wide = BeamSearch(cost=ProgramSize(), beam_width=10, max_depth=2).find(task, ATOMIC_LIBRARY)
    full = Enumerate(max_depth=2).find(task, ATOMIC_LIBRARY)
    assert len(wide.programs) == 1
    assert wide.stats.considered < full.stats.considered
