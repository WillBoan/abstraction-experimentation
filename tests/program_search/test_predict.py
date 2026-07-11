"""``predict`` (apply-to-test) and the parameterized ARC scoring rules."""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.core.task import Example, Task
from arc_lab.eval.scoring import score_task, score_test_input
from arc_lab.program_search.execution.predict import predict
from arc_lab.program_search.substrate.library import Library, Primitive
from arc_lab.program_search.substrate.program import Apply, Input, Program
from arc_lab.program_search.substrate.types import GRID

_IN = Grid.from_list([[1, 2], [3, 4]])
_FLIPPED = Grid.from_list([[2, 1], [4, 3]])


def _boom(grid: Grid) -> Grid:
    raise ValueError("undefined here")


_LIBRARY = Library(
    name="predict-test",
    primitives=(
        Primitive(name="identity", param_types=(GRID,), return_type=GRID, impl=lambda g: g),
        Primitive(
            name="flip_h",
            param_types=(GRID,),
            return_type=GRID,
            impl=lambda g: Grid(g.array[:, ::-1]),
        ),
        Primitive(name="boom", param_types=(GRID,), return_type=GRID, impl=_boom),
    ),
)

_IDENTITY: Program = Apply("identity", (Input(),))
_IDENTITY_TWICE: Program = Apply("identity", (Apply("identity", (Input(),)),))
_FLIP: Program = Apply("flip_h", (Input(),))
_BOOM: Program = Apply("boom", (Input(),))


def test_predict_takes_top_k_in_rank_order() -> None:
    prediction = predict([_IDENTITY, _FLIP], [_IN], _LIBRARY, attempts_per_test=2)
    assert prediction == [[_IN, _FLIPPED]]


def test_predict_dedups_equal_outputs_and_backfills() -> None:
    # identity twice produces the same grid — the second attempt must fall to flip.
    prediction = predict([_IDENTITY, _IDENTITY_TWICE, _FLIP], [_IN], _LIBRARY, attempts_per_test=2)
    assert prediction == [[_IN, _FLIPPED]]


def test_predict_skips_raising_programs() -> None:
    prediction = predict([_BOOM, _FLIP], [_IN], _LIBRARY, attempts_per_test=2)
    assert prediction == [[_FLIPPED]]


def test_predict_all_raise_yields_empty_candidates() -> None:
    assert predict([_BOOM], [_IN], _LIBRARY) == [[]]


def test_predict_respects_attempt_cap_per_input() -> None:
    prediction = predict([_IDENTITY, _FLIP], [_IN, _FLIPPED], _LIBRARY, attempts_per_test=1)
    assert prediction == [[_IN], [_FLIPPED]]


def test_scoring_attempts_parameter() -> None:
    # the right answer is ranked second: 2 attempts solve it, 1 attempt does not.
    assert score_test_input([_IN, _FLIPPED], _FLIPPED, attempts=2) is True
    assert score_test_input([_IN, _FLIPPED], _FLIPPED, attempts=1) is False


def test_score_task_end_to_end_with_predict() -> None:
    task = Task(
        task_id="t",
        train=(Example(input=_IN, output=_FLIPPED),),
        test=(Example(input=_IN, output=_FLIPPED),),
    )
    prediction = predict([_IDENTITY, _FLIP], [ex.input for ex in task.test], _LIBRARY)
    solved, per_test = score_task(task, prediction)
    assert solved is True
    assert per_test == (True,)
    solved_strict, _ = score_task(task, prediction, attempts=1)
    assert solved_strict is False
