from __future__ import annotations

import pytest

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task
from arc_lab.solvers.dsl.search import SingleApply
from arc_lab.solvers.dsl.solver import GeometricSearchSolver, ProgramSearchSolver
from arc_lab.solvers.dsl.substrate import (
    Apply,
    Const,
    Input,
    Library,
    Primitive,
    Program,
    ValueType,
)
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY

_G = Grid.from_list


# -- library ------------------------------------------------------------


def test_library_get_and_names() -> None:
    assert "rot90" in D4_LIBRARY.names()
    assert D4_LIBRARY.get("rot90").arity == 1
    with pytest.raises(KeyError):
        D4_LIBRARY.get("does_not_exist")


def test_library_rejects_duplicate_names() -> None:
    dup = D4_LIBRARY.get("identity")
    with pytest.raises(ValueError):
        Library(name="bad", primitives=(dup, dup))


def test_library_extended_grows_and_bumps_version() -> None:
    extra = Primitive("noop", (ValueType.GRID,), ValueType.GRID, lambda g: g)
    grown = D4_LIBRARY.extended(name="d4+", extra=(extra,))
    assert grown.version == D4_LIBRARY.version + 1
    assert "noop" in grown.names()
    assert "noop" not in D4_LIBRARY.names()  # original is untouched


def test_unary_grid_primitives_are_all_eight() -> None:
    assert len(list(D4_LIBRARY.unary_grid_primitives())) == 8


# -- program semantics --------------------------------------------------


def test_evaluate_input_is_identity() -> None:
    g = _G([[1, 2], [3, 4]])
    assert Input().evaluate(g, D4_LIBRARY) == g


def test_evaluate_apply_transpose() -> None:
    prog = Apply("transpose", (Input(),))
    assert prog.evaluate(_G([[1, 2], [3, 4]]), D4_LIBRARY) == _G([[1, 3], [2, 4]])


# -- structural methods -------------------------------------------------


def test_children() -> None:
    assert Input().children() == ()
    assert Const(5, ValueType.INT).children() == ()
    inner = Apply("rot90", (Input(),))
    assert Apply("flip_v", (inner,)).children() == (inner,)


def test_size_and_depth() -> None:
    prog = Apply("flip_v", (Apply("rot90", (Input(),)),))
    assert prog.size() == 3  # flip_v, rot90, input
    assert prog.depth() == 3
    assert Input().size() == 1
    assert Input().depth() == 1


def test_walk_yields_every_node() -> None:
    inner = Apply("rot90", (Input(),))
    prog = Apply("flip_v", (inner,))
    assert list(prog.walk()) == [prog, inner, Input()]


def test_result_type() -> None:
    assert Input().result_type(D4_LIBRARY) == ValueType.GRID
    assert Const(3, ValueType.COLOR).result_type(D4_LIBRARY) == ValueType.COLOR
    assert Apply("rot90", (Input(),)).result_type(D4_LIBRARY) == ValueType.GRID


# -- serialisation (programs are data) ---------------------------------


def test_program_roundtrip() -> None:
    prog = Apply("flip_v", (Apply("rot90", (Input(),)),))
    assert Program.from_dict(prog.to_dict()) == prog


def test_from_dict_rejects_garbage() -> None:
    with pytest.raises(ValueError):
        Program.from_dict({"op": "nonsense"})


# -- search + solver ----------------------------------------------------


def test_single_apply_finds_flip() -> None:
    task = Task.from_dict(
        "t",
        {
            "train": [{"input": [[1, 2]], "output": [[2, 1]]}],
            "test": [{"input": [[3, 4]], "output": [[4, 3]]}],
        },
    )
    found = SingleApply().find(task, D4_LIBRARY).programs
    assert Apply("flip_h", (Input(),)) in found


def test_geometric_solver_is_program_search_solver() -> None:
    solver = GeometricSearchSolver()
    assert isinstance(solver, ProgramSearchSolver)
    assert solver.name == "dsl"


def test_program_search_solver_fallback_returns_input() -> None:
    # No geometric transform fits; solver must still return the input grid.
    task = Task.from_dict(
        "t",
        {
            "train": [{"input": [[1]], "output": [[2]]}],
            "test": [{"input": [[3]], "output": [[3]]}],
        },
    )
    assert GeometricSearchSolver().predict(task) == [[_G([[3]])]]
