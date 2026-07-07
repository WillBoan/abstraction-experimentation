"""The lambda-index substrate: `build_grid` + De Bruijn `$i` bound variables.

Validates the keystone by *hand-written* programs (no search this session): a single
size-general `build_grid` program re-derives each D4 member via coordinate arithmetic, De Bruijn
indices resolve correctly, the new nodes round-trip, and a `build_grid` template mints cleanly as
an abstraction (loop vars stay internal — only `#0` is an argument).
"""

from __future__ import annotations

import numpy as np

from arc_lab.core.grid import Grid
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
from arc_lab.solvers.dsl.substrate.primitives.build import BUILD_LIBRARY
from arc_lab.solvers.dsl.substrate.program import Apply, Const, Input, Lam, Param, Program, Var
from arc_lab.solvers.dsl.substrate.types import ValueType

_G = ValueType.GRID
_INT = ValueType.INT
_LIB = BUILD_LIBRARY

# Non-square shapes on purpose — a fixed-coordinate program can't fit; only size-general ones do.
_GRIDS = [
    Grid.from_list([[1, 2], [3, 4]]),
    Grid.from_list([[1, 2, 3], [4, 5, 6]]),
    Grid.from_list([[1, 2], [3, 4], [5, 6]]),
]


# -- program builders: D4 members as coordinate lambdas over a grid sub-program `g` --


def _read(g: Program, row: Program, col: Program) -> Program:
    return Apply("read", (g, row, col))


def _sub(a: Program, b: Program) -> Program:
    return Apply("sub", (a, b))


def _w(g: Program) -> Program:
    return Apply("width", (g,))


def _h(g: Program) -> Program:
    return Apply("height", (g,))


def _one() -> Program:
    return Const(1, _INT)


def _rot90(g: Program) -> Program:
    # out shape (width, height); out[i][j] = read(g, j, width-1-i). $0 = col j, $1 = row i.
    body = _read(g, Var(0, _INT), _sub(_sub(_w(g), _one()), Var(1, _INT)))
    return Apply("build_grid", (_w(g), _h(g), Lam(Lam(body))))


def _flip_h(g: Program) -> Program:
    # out shape (height, width); out[i][j] = read(g, i, width-1-j).
    body = _read(g, Var(1, _INT), _sub(_sub(_w(g), _one()), Var(0, _INT)))
    return Apply("build_grid", (_h(g), _w(g), Lam(Lam(body))))


def _transpose(g: Program) -> Program:
    # out shape (width, height); out[i][j] = read(g, j, i).
    body = _read(g, Var(0, _INT), Var(1, _INT))
    return Apply("build_grid", (_w(g), _h(g), Lam(Lam(body))))


# -- size-general re-derivation: one program, every shape --


def test_build_grid_rederives_rot90_size_general() -> None:
    prog = _rot90(Input())
    for g in _GRIDS:
        assert prog.evaluate_grid(g, _LIB) == Grid(np.rot90(g.array, 1))


def test_build_grid_rederives_flip_h_size_general() -> None:
    prog = _flip_h(Input())
    for g in _GRIDS:
        assert prog.evaluate_grid(g, _LIB) == Grid(np.fliplr(g.array))


def test_build_grid_rederives_transpose_size_general() -> None:
    prog = _transpose(Input())
    for g in _GRIDS:
        assert prog.evaluate_grid(g, _LIB) == Grid(g.array.T)


# -- De Bruijn correctness: $0 innermost (col), $1 outer (row) --


def test_de_bruijn_inner_and_outer_indices() -> None:
    g = Grid.from_list([[0, 0], [0, 0]])  # ignored; the body reads only bound vars
    # body = $1 (outer = row i) → cell (i,j) = i
    rows = Apply("build_grid", (Const(2, _INT), Const(3, _INT), Lam(Lam(Var(1, _INT)))))
    assert rows.evaluate_grid(g, _LIB) == Grid.from_list([[0, 0, 0], [1, 1, 1]])
    # body = $0 (inner = col j) → cell (i,j) = j
    cols = Apply("build_grid", (Const(2, _INT), Const(3, _INT), Lam(Lam(Var(0, _INT)))))
    assert cols.evaluate_grid(g, _LIB) == Grid.from_list([[0, 1, 2], [0, 1, 2]])


# -- inspectable data: round-trip + Stitch notation --


def test_build_grid_program_round_trips() -> None:
    prog = _rot90(Input())  # exercises build_grid + Lam + Var + Apply + Input + Const
    assert Program.from_dict(prog.to_dict()) == prog


def test_var_and_param_use_stitch_notation() -> None:
    assert str(Lam(Lam(Var(0, _INT)))) == "lam(lam($0))"
    assert str(Param(0, _G)) == "#0"  # abstraction var #j, distinct from bound var $i


# -- the two-channel payoff: a build_grid program mints as an abstraction --


def test_build_grid_template_is_abstractable() -> None:
    # A closed rot90 template over Param(0) (the grid arg). Minting it must give a (GRID)->GRID
    # primitive of arity 1: the loop vars ($i) stay internal; only #0 counts as an argument —
    # exactly the separation that lets a size-general geometry program become a learned primitive.
    rot90 = make_abstraction("rot90", _rot90(Param(0, _G)), _LIB)
    assert rot90.param_types == (_G,)
    assert rot90.return_type == _G
    for g in _GRIDS:
        assert rot90.impl(g) == Grid(np.rot90(g.array, 1))
