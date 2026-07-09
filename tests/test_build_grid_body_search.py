"""Generic open-body ``build_grid`` search over the complete low floor.

This is the machinery step beyond geometric coordinate search: the search should synthesize a
size-general per-cell branch, not just a coordinate transform. The target below is a binary mask of
where the input equals color 2.
"""

from __future__ import annotations

from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search import BuildGridBodySearch
from arc_lab.solvers.dsl.search.type_directed import candidate_applications
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.primitives.build import BUILD_GRID, HEIGHT, WIDTH
from arc_lab.solvers.dsl.substrate.primitives.cells import READ
from arc_lab.solvers.dsl.substrate.primitives.control import EQ, IF
from arc_lab.solvers.dsl.substrate.program import Const
from arc_lab.solvers.dsl.substrate.types import BOOL, COLOR, INT


def _task() -> Task:
    # A size-general per-cell mask (output = 1 where input == 3, else 0). Two *differently shaped*
    # examples force a genuine per-cell conditional and size-general dims — the smallest task that
    # still exercises the whole if/eq/read + build_grid path (kept minimal so the test is fast).
    return Task.from_dict(
        "cell-branch",
        {
            "train": [
                {"input": [[3, 0], [0, 3]], "output": [[1, 0], [0, 1]]},
                {"input": [[0, 3, 3]], "output": [[0, 1, 1]]},
            ],
            # test input stays within the training alphabet {0, 3} — an unseen color's mask value is
            # genuinely underdetermined by training, so probing one would test luck, not functionality.
            "test": [{"input": [[0, 3], [3, 0]], "output": [[0, 1], [1, 0]]}],
        },
    )


def _library() -> Library:
    return Library(
        name="complete-floor-min",
        primitives=(READ, WIDTH, HEIGHT, BUILD_GRID, EQ, IF),
    )


def test_finds_a_per_cell_conditional_build_grid_program() -> None:
    task = _task()
    library = _library()
    # Deliberately minimal search budget — this locks *functionality* (that a per-cell if/eq/read body
    # is found), not throughput. `int_consts=()` because the body's coordinates come from the cell Vars
    # ($0/$1), never INT literals, so INT consts would only bloat `eq`/`read` enumeration. A tight beam
    # suffices for this small task; harder tasks bump it explicitly (see BuildGridBodySearch defaults).
    result = BuildGridBodySearch(beam_width=12, int_consts=()).find(task, library)
    assert len(result.programs) == 1
    program = str(result.programs[0])
    assert program.startswith("build_grid(")
    assert "if(" in program and "eq(" in program and "read(" in program
    ex = task.test[0]
    assert result.programs[0].evaluate_grid(ex.input, library) == ex.output


def test_result_targets_bind_polymorphic_returns_before_argument_search() -> None:
    candidates = [
        (Const(False, BOOL), BOOL),
        (Const(True, BOOL), BOOL),
        (Const(0, COLOR), COLOR),
        (Const(1, COLOR), COLOR),
        (Const(0, INT), INT),
        (Const(1, INT), INT),
    ]

    applications = list(
        candidate_applications(IF, value_candidates=candidates, result_targets=(COLOR,))
    )

    assert applications
    assert all(result_type == COLOR for _, result_type in applications)
    for args, _ in applications:
        assert len(args) == 3
        assert isinstance(args[0], Const) and args[0].value_type == BOOL
        assert isinstance(args[1], Const) and args[1].value_type == COLOR
        assert isinstance(args[2], Const) and args[2].value_type == COLOR
