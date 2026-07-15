"""Tests for the abstraction mechanism: Param nodes + template-evaluating primitives."""

from __future__ import annotations

import numpy as np
import pytest
from arc_lab.solvers.dsl.search import Enumerate
from arc_lab.solvers.dsl.substrate.abstraction import make_abstraction
from arc_lab.solvers.dsl.substrate.library import Library
from arc_lab.solvers.dsl.substrate.primitives.geometry import D4_LIBRARY
from arc_lab.solvers.dsl.substrate.program import Apply, Input, Param, Program
from arc_lab.solvers.dsl.substrate.types import GRID

from arc_lab.core.grid import Grid
from arc_lab.core.task import Task

_G = GRID

#: The two D4 generators — the E1 starting library. rot90 is withheld (it's the target).
_GENERATORS = Library(
    name="generators",
    primitives=(D4_LIBRARY.get("flip_h"), D4_LIBRARY.get("transpose")),
)


def _rot90_template() -> Program:
    """rot90 as a closed template over the generators: transpose(flip_h(#0))."""
    return Apply("transpose", (Apply("flip_h", (Param(0, _G),)),))


def _rot90_task() -> Task:
    def pair(rows: list[list[int]]) -> dict[str, object]:
        return {"input": rows, "output": np.rot90(np.array(rows, dtype=np.int8), 1).tolist()}

    return Task.from_dict(
        "rot",
        {
            "train": [pair([[1, 2, 3], [4, 5, 6]]), pair([[2, 0, 1], [3, 4, 5]])],
            "test": [pair([[7, 8], [9, 0]])],
        },
    )


# -- Param node + env ---------------------------------------------------


def test_param_reads_from_env() -> None:
    g = Grid.from_list([[1, 2]])
    # The dummy grid is irrelevant; the value comes from env[index].
    assert Param(0, _G).evaluate(Grid.from_list([[0]]), _GENERATORS, (g,)) == g


def test_template_round_trips_through_dict() -> None:
    template = _rot90_template()
    assert Program.from_dict(template.to_dict()) == template
    assert str(template) == "transpose(flip_h(#0))"


# -- make_abstraction ---------------------------------------------------


def test_abstraction_computes_rot90_and_types() -> None:
    rot90 = make_abstraction("rot90", _rot90_template(), _GENERATORS)
    g = Grid.from_list([[1, 2, 3], [4, 5, 6]])
    assert rot90.impl(g) == Grid(np.rot90(g.array, 1))
    assert rot90.param_types == (_G,)
    assert rot90.return_type == _G
    assert rot90.template == _rot90_template()


def test_learned_primitive_serialises_its_template() -> None:
    rot90 = make_abstraction("rot90", _rot90_template(), _GENERATORS)
    data = rot90.to_dict()
    assert data["name"] == "rot90"
    assert data["template"] == _rot90_template().to_dict()


def test_template_must_be_closed() -> None:
    with pytest.raises(ValueError, match="closed"):
        make_abstraction("bad", Apply("flip_h", (Input(),)), _GENERATORS)


def test_param_indices_must_be_contiguous() -> None:
    with pytest.raises(ValueError, match="contiguous"):
        make_abstraction("bad", Apply("flip_h", (Param(1, _G),)), _GENERATORS)


# -- the payoff: a learned abstraction collapses search depth -----------


def test_abstraction_collapses_depth() -> None:
    task = _rot90_task()
    rot90 = make_abstraction("rot90", _rot90_template(), _GENERATORS)
    extended = _GENERATORS.extended(name="generators+rot90", extra=(rot90,))

    # Generators alone: rot90 is a depth-2 word (out of reach at depth 1).
    assert Enumerate(max_depth=1).find(task, _GENERATORS).programs == ()
    assert Enumerate(max_depth=2).find(task, _GENERATORS).programs != ()

    # With the learned abstraction: solved at depth 1 by a single application.
    solved = Enumerate(max_depth=1).find(task, extended).programs
    assert solved == (Apply("rot90", (Input(),)),)
