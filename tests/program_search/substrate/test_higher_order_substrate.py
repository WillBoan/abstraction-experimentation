"""Substrate HO changes: ``Lam`` carries its binder type (typing as a precise arrow), and
``build_grid``'s hole is the curried coordinate arrow that a synthesized ``Lam`` unifies with."""

from __future__ import annotations

from arc_lab.core.grid import Grid
from arc_lab.program_search.substrate.library import Library
from arc_lab.program_search.substrate.primitives.build import BUILD_GRID
from arc_lab.program_search.substrate.program import Apply, Const, Lam, Program
from arc_lab.program_search.substrate.types import COLOR, INT, ArrowType, unify

_LIB = Library(name="build", primitives=(BUILD_GRID,))
_CELL_FN = ArrowType((INT,), ArrowType((INT,), COLOR))


def test_lam_result_type_is_a_precise_arrow() -> None:
    lam = Lam(param_type=INT, body=Const(value=5, value_type=COLOR))
    assert lam.result_type(_LIB) == ArrowType((INT,), COLOR)


def test_nested_lam_types_as_and_unifies_with_build_grids_hole() -> None:
    cell = Lam(param_type=INT, body=Lam(param_type=INT, body=Const(value=5, value_type=COLOR)))
    assert cell.result_type(_LIB) == _CELL_FN
    assert BUILD_GRID.param_types[2] == _CELL_FN
    assert unify(BUILD_GRID.param_types[2], cell.result_type(_LIB)) == {}


def test_lam_round_trips_through_serialization() -> None:
    lam = Lam(param_type=INT, body=Lam(param_type=INT, body=Const(value=5, value_type=COLOR)))
    assert Program.from_dict(lam.to_dict()) == lam


def test_build_grid_program_evaluates() -> None:
    cell = Lam(param_type=INT, body=Lam(param_type=INT, body=Const(value=5, value_type=COLOR)))
    program = Apply(
        primitive="build_grid",
        args=(Const(value=2, value_type=INT), Const(value=2, value_type=INT), cell),
    )
    result = program.evaluate(Grid.from_list([[0]]), _LIB)
    assert result == Grid.from_list([[5, 5], [5, 5]])
