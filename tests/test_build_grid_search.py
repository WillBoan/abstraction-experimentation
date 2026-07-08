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
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.primitives.build import BUILD_AFFINE_LIBRARY, BUILD_LIBRARY
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Param, Program
from arc_lab.solvers.dsl.substrate.types import ValueType

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


# -- primitive-driven coordinate grammar (composes learned/affine INT ops) ----------


def test_composes_signature() -> None:
    # The search's declared composition rule: it composes INT^n -> INT coordinate primitives only.
    s = BuildGridSearch()
    _int, _grid, _color = ValueType.INT, ValueType.GRID, ValueType.COLOR
    assert s.composes_signature((_int, _int), _int)  # sub / add / mul / a learned mirror_index
    assert s.composes_signature((_int,), _int)
    assert not s.composes_signature((_grid, _int), _int)  # a GRID param is not a coordinate op
    assert not s.composes_signature((_int, _int), _color)  # a COLOR result is not a coordinate
    assert not s.composes_signature((), _int)  # nullary


def test_affine_grammar_composes_add_and_mul() -> None:
    # The pool is primitive-driven: on the affine library it gains add/mul; sub-only composes neither.
    rot90 = _task(lambda a: np.rot90(a, 1))
    pairs = [(ex.input, ex.output) for ex in rot90.train if ex.output is not None]
    battery = [
        (inp, i, j) for inp, out in pairs for i in range(out.height) for j in range(out.width)
    ]

    def composed_ops(library: Library) -> set[str]:
        pool = BuildGridSearch()._coordinate_pool(battery, rot90, library)
        return {n.primitive for expr in pool for n in expr.walk() if isinstance(n, Apply)}

    assert not {"add", "mul"} & composed_ops(BUILD_LIBRARY)
    assert {"add", "mul"} <= composed_ops(BUILD_AFFINE_LIBRARY)


def _mirror_index_library() -> Library:
    _int = ValueType.INT
    mirror = Apply("sub", (Apply("sub", (Param(0, _int), Param(1, _int))), Const(1, _int)))
    return BUILD_LIBRARY.extended(
        name="build+mirror", extra=(make_abstraction("mirror_index", mirror, BUILD_LIBRARY),)
    )


def test_search_reuses_a_learned_mirror_index() -> None:
    # At a tight beam the raw depth-2 reflection `sub(sub(width,$1),1)` is cut, but a learned
    # mirror_index is a depth-1 coordinate the search composes -> the reflection becomes reachable
    # again (the beam-cliff dissolution, in miniature).
    rot90 = _task(lambda a: np.rot90(a, 1))
    assert not BuildGridSearch(beam_width=64).find(rot90, BUILD_LIBRARY).programs
    assert BuildGridSearch(beam_width=64).find(rot90, _mirror_index_library()).programs
